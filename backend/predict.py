# backend/predict.py
import torch
import torch.nn as nn
import logging
from config import MODEL_CONFIG, DEVICE, Z_BATCH_SIZE

# ==================================================================
# COPIA Y PEGA AQUÍ LAS CLASES DE TU MODELO EXACTAMENTE COMO LAS TIENES
# ConvLSTMCell, ConvLSTM2DLayer, ConvLSTM3D_Enhanced
# ... (por brevedad, no las pego aquí, pero deben ir en este archivo)
# ==================================================================
class ConvLSTMCell(nn.Module):
    def __init__(self, input_dim, hidden_dim, kernel_size, bias=True):
        super(ConvLSTMCell, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.kernel_size = kernel_size
        self.padding = kernel_size[0] // 2, kernel_size[1] // 2
        self.bias = bias
        self.conv = nn.Conv2d(in_channels=self.input_dim + self.hidden_dim,
                              out_channels=4 * self.hidden_dim,
                              kernel_size=self.kernel_size,
                              padding=self.padding,
                              bias=self.bias)

    def forward(self, input_tensor, cur_state):
        h_cur, c_cur = cur_state
        combined = torch.cat([input_tensor, h_cur], dim=1)
        combined_conv = self.conv(combined)
        cc_i, cc_f, cc_o, cc_g = torch.split(combined_conv, self.hidden_dim, dim=1)
        i = torch.sigmoid(cc_i); f = torch.sigmoid(cc_f); o = torch.sigmoid(cc_o); g = torch.tanh(cc_g)
        c_next = f * c_cur + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next

    def init_hidden(self, batch_size, image_size, device):
        height, width = image_size
        return (torch.zeros(batch_size, self.hidden_dim, height, width, device=device),
                torch.zeros(batch_size, self.hidden_dim, height, width, device=device))

class ConvLSTM2DLayer(nn.Module):
    def __init__(self, input_dim, hidden_dim, kernel_size, use_layer_norm=True, img_size=(500,500), bias=True, return_all_layers=False):
        super(ConvLSTM2DLayer, self).__init__()
        self.use_layer_norm = use_layer_norm
        self.return_all_layers = return_all_layers
        self.cell = ConvLSTMCell(input_dim, hidden_dim, kernel_size, bias=bias)
        if self.use_layer_norm:
            self.layer_norm = nn.LayerNorm([hidden_dim, img_size[0], img_size[1]])

    def forward(self, input_tensor, hidden_state=None):
        b, seq_len, _, h, w = input_tensor.size()
        if hidden_state is None:
            hidden_state = self.cell.init_hidden(b, (h, w), input_tensor.device)
        
        output_list = []
        h_cur, c_cur = hidden_state
        for t in range(seq_len):
            h_cur, c_cur = self.cell(input_tensor=input_tensor[:, t, :, :, :], cur_state=[h_cur, c_cur])
            output_list.append(h_cur)
            
        if self.return_all_layers:
            layer_output = torch.stack(output_list, dim=1)
            if self.use_layer_norm:
                B, T, C, H, W = layer_output.shape
                output_reshaped = layer_output.contiguous().view(B * T, C, H, W)
                normalized_output = self.layer_norm(output_reshaped)
                layer_output = normalized_output.view(B, T, C, H, W)
        else:
            layer_output = h_cur.unsqueeze(1)
        return layer_output, (h_cur, c_cur)

class ConvLSTM3D_Enhanced(nn.Module):
    def __init__(self, input_dim, hidden_dims, kernel_sizes, num_layers, pred_steps, use_layer_norm, img_height, img_width):
        super(ConvLSTM3D_Enhanced, self).__init__()
        self.input_dim = input_dim
        self.pred_steps = pred_steps
        self.layers = nn.ModuleList()
        current_dim = self.input_dim
        for i in range(num_layers):
            is_last_layer = (i == num_layers - 1)
            self.layers.append(
                ConvLSTM2DLayer(
                    input_dim=current_dim, hidden_dim=hidden_dims[i], kernel_size=kernel_sizes[i],
                    use_layer_norm=use_layer_norm, img_size=(img_height, img_width),
                    return_all_layers=not is_last_layer, bias=True
                ))
            current_dim = hidden_dims[i]
        self.output_conv = nn.Conv3d(in_channels=hidden_dims[-1], out_channels=self.pred_steps * self.input_dim,
                                     kernel_size=(1, 3, 3), padding=(0, 1, 1))
        self.sigmoid = nn.Sigmoid()
        nn.init.xavier_uniform_(self.output_conv.weight)
        nn.init.zeros_(self.output_conv.bias)

    def forward(self, x):
        b, seq_len, c, h, w = x.shape
        current_input = x
        hidden_states = [None] * len(self.layers)
        for i, layer in enumerate(self.layers):
            current_input, hidden_states[i] = layer(current_input, hidden_states[i])
        output_for_conv3d = current_input.permute(0, 2, 1, 3, 4)
        raw_conv_output = self.output_conv(output_for_conv3d)
        prediction_features = raw_conv_output.squeeze(2)
        predictions_norm = self.sigmoid(prediction_features.view(b, self.pred_steps, self.input_dim, h, w))
        return predictions_norm


class ModelPredictor:
    def __init__(self, model_path):
        self.model = self._load_model(model_path)

    def _load_model(self, model_path):
        logging.info(f"Cargando modelo desde: {model_path}")
        try:
            model = ConvLSTM3D_Enhanced(**MODEL_CONFIG)
            checkpoint = torch.load(model_path, map_location=DEVICE, weights_only=True)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.to(DEVICE)
            model.eval()
            logging.info("Modelo cargado exitosamente.")
            return model
        except Exception as e:
            logging.error(f"Error fatal al cargar el modelo: {e}", exc_info=True)
            raise

    def predict(self, input_volume: torch.Tensor) -> torch.Tensor:
        x_to_model_full = input_volume.permute(0, 1, 4, 2, 3).to(DEVICE)
        
        num_z_levels = x_to_model_full.shape[0]
        all_predictions_chunks = []

        logging.info(f"Iniciando predicción en {num_z_levels} niveles de altura...")
        for z_start in range(0, num_z_levels, Z_BATCH_SIZE):
            z_end = min(z_start + Z_BATCH_SIZE, num_z_levels)
            x_chunk = x_to_model_full[z_start:z_end, ...]
            
            with torch.no_grad(), torch.amp.autocast(device_type="cuda"):
                prediction_chunk = self.model(x_chunk)
            
            all_predictions_chunks.append(prediction_chunk.cpu())
        
        prediction_norm = torch.cat(all_predictions_chunks, dim=0)
        logging.info("Predicción completada.")
        
        del x_to_model_full, all_predictions_chunks
        torch.cuda.empty_cache()

        return prediction_norm