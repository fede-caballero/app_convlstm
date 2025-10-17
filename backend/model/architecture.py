import torch
import torch.nn as nn
import logging
from torch.utils.checkpoint import checkpoint

class SelfAttention(nn.Module):
    """ Capa de Self-Attention Espacial """
    def __init__(self, in_dim):
        super(SelfAttention, self).__init__()
        self.query_conv = nn.Conv2d(in_channels=in_dim, out_channels=in_dim // 8, kernel_size=1)
        self.key_conv = nn.Conv2d(in_channels=in_dim, out_channels=in_dim // 8, kernel_size=1)
        self.value_conv = nn.Conv2d(in_channels=in_dim, out_channels=in_dim, kernel_size=1)
        self.gamma = nn.Parameter(torch.zeros(1))
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, x):
        # x: (B, C, H, W)
        B, C, H, W = x.size()
        proj_query = self.query_conv(x).view(B, -1, W * H).permute(0, 2, 1)
        proj_key = self.key_conv(x).view(B, -1, W * H)
        energy = torch.bmm(proj_query, proj_key)
        attention = self.softmax(energy)
        proj_value = self.value_conv(x).view(B, -1, W * H)

        out = torch.bmm(proj_value, attention.permute(0, 2, 1))
        out = out.view(B, C, H, W)

        out = self.gamma * out + x
        return out, attention

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
        nn.init.xavier_uniform_(self.conv.weight)
        if self.bias:
            nn.init.zeros_(self.conv.bias)

    def forward(self, input_tensor, cur_state):
        h_cur, c_cur = cur_state
        combined = torch.cat([input_tensor, h_cur], dim=1)
        combined_conv = self.conv(combined)
        cc_i, cc_f, cc_o, cc_g = torch.split(combined_conv, self.hidden_dim, dim=1)
        i = torch.sigmoid(cc_i)
        f = torch.sigmoid(cc_f)
        o = torch.sigmoid(cc_o)
        g = torch.tanh(cc_g)
        c_next = f * c_cur + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next

    def init_hidden(self, batch_size, image_size, device):
        height, width = image_size
        return (torch.zeros(batch_size, self.hidden_dim, height, width, device=device),
                torch.zeros(batch_size, self.hidden_dim, height, width, device=device))

class ConvLSTM2DLayer(nn.Module):
    def __init__(self, input_dim, hidden_dim, kernel_size, use_layer_norm, img_size, return_all_layers=False):
        super(ConvLSTM2DLayer, self).__init__()
        self.cell = ConvLSTMCell(input_dim, hidden_dim, kernel_size)
        self.use_layer_norm = use_layer_norm
        self.return_all_layers = return_all_layers
        if self.use_layer_norm:
            self.layer_norm = nn.LayerNorm([hidden_dim, img_size[0], img_size[1]])

    def forward(self, input_tensor, hidden_state=None):
        b, seq_len, _, h, w = input_tensor.size()
        device = input_tensor.device
        if hidden_state is None:
            hidden_state = self.cell.init_hidden(b, (h, w), device)

        layer_output_list = []
        h_cur, c_cur = hidden_state
        for t in range(seq_len):
            h_cur, c_cur = self.cell(input_tensor=input_tensor[:, t, :, :, :], cur_state=[h_cur, c_cur])
            layer_output_list.append(h_cur)

        if self.return_all_layers:
            layer_output = torch.stack(layer_output_list, dim=1)
            if self.use_layer_norm:
                B_ln, T_ln, C_ln, H_ln, W_ln = layer_output.shape
                output_reshaped = layer_output.contiguous().view(B_ln * T_ln, C_ln, H_ln, W_ln)
                normalized_output = self.layer_norm(output_reshaped)
                layer_output = normalized_output.view(B_ln, T_ln, C_ln, H_ln, W_ln)
        else:
            layer_output = h_cur.unsqueeze(1)

        return layer_output, (h_cur, c_cur)

class Seq2Seq(nn.Module):
    def __init__(self, config):
        super(Seq2Seq, self).__init__()
        self.config = config
        self.num_layers = config['model_num_layers']
        self.hidden_dims = config['model_hidden_dims']
        
        self.layers = nn.ModuleList()
        current_dim = config['model_input_dim']
        for i in range(self.num_layers):
            is_last_layer = (i == self.num_layers - 1)
            self.layers.append(
                ConvLSTM2DLayer(
                    input_dim=current_dim,
                    hidden_dim=self.hidden_dims[i],
                    kernel_size=config['model_kernel_sizes'][i],
                    use_layer_norm=config['model_use_layer_norm'],
                    img_size=config['downsample_size'],
                    return_all_layers=not is_last_layer
                )
            )
            current_dim = self.hidden_dims[i]

        if self.config.get('use_attention', False):
            self.attention = SelfAttention(self.hidden_dims[-1])
            logging.info("Mecanismo de atención espacial activado.")

        self.output_conv = nn.Conv3d(
            in_channels=self.hidden_dims[-1],
            out_channels=config['model_input_dim'] * config['pred_len'],
            kernel_size=(1, 3, 3),
            padding=(0, 1, 1)
        )
        self.sigmoid = nn.Sigmoid()
        nn.init.xavier_uniform_(self.output_conv.weight)
        nn.init.zeros_(self.output_conv.bias)
        logging.info(f"Modelo Seq2Seq creado: {self.num_layers} capas, Hidden dims: {self.hidden_dims}")

    def forward(self, x_volumetric):
        num_z_levels, b, seq_len, h, w, c_in = x_volumetric.shape
        all_level_predictions = []

        for z_idx in range(num_z_levels):
            current_input = x_volumetric[z_idx, ...].permute(0, 1, 4, 2, 3)
            hidden_states = [None] * self.num_layers

            for i in range(self.num_layers):
                layer_input = current_input
                layer_output, hidden_state = checkpoint(self.layers[i], layer_input, hidden_states[i], use_reentrant=False)
                hidden_states[i] = hidden_state
                current_input = layer_output

            # Aplicar atención si está activada
            if hasattr(self, 'attention'):
                # La salida de la última capa es (B, 1, C, H, W), la quitamos para la atención
                attention_input = current_input.squeeze(1)
                attention_output, _ = self.attention(attention_input)
                # Añadimos la dimensión de nuevo para la convolución 3D
                current_input = attention_output.unsqueeze(1)

            output_for_conv3d = current_input.permute(0, 2, 1, 3, 4)
            raw_conv_output = self.output_conv(output_for_conv3d)
            
            pred_features = raw_conv_output.squeeze(2)
            level_pred = pred_features.view(b, self.config['pred_len'], self.config['model_input_dim'], h, w)
            level_pred = level_pred.permute(0, 1, 3, 4, 2)
            level_pred = self.sigmoid(level_pred)
            all_level_predictions.append(level_pred)

        return torch.stack(all_level_predictions, dim=0)
