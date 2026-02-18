import os
import sys
import torch
import time
import yaml

# 1. ARREGLAR IMPORTS
# Agregamos la carpeta raíz del proyecto al path para que Python encuentre 'backend'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

# Ahora sí podemos importar tu clase real
from backend.model.architecture import ConvLSTM3D_Enhanced

def main():
    # Ruta a tu archivo de modelo
    checkpoint_path = "phase3_refinement_epoch_99.pth" 
    
    if not os.path.exists(checkpoint_path):
        print(f"ERROR: No encuentro el archivo {checkpoint_path}")
        return

    print(f"Cargando checkpoint desde {checkpoint_path}...")
    
    # 2. CARGAR EL CHECKPOINT
    # map_location='cpu' es vital para moverlo de GPU a CPU
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # 3. RECUPERAR CONFIGURACIÓN AUTOMÁTICAMENTE
    # Tu train.py guarda la 'config' dentro del archivo .pth, ¡usémosla!
    if 'config' in checkpoint:
        config = checkpoint['config']
        print("Configuración recuperada exitosamente del archivo.")
    else:
        print("Error: El checkpoint no tiene la configuración guardada.")
        return

    # Extraer parámetros necesarios
    model_conf = config['model']
    data_conf = config['data']
    
    # 4. INSTANCIAR EL MODELO CORRECTO
    print("Construyendo el modelo...")
    model = ConvLSTM3D_Enhanced(
        input_dim=model_conf['input_dim'],
        hidden_dims=model_conf['hidden_dims'],
        kernel_sizes=model_conf['kernel_sizes'],
        num_layers=model_conf['num_layers'],
        pred_steps=data_conf['prediction_steps'],
        use_layer_norm=model_conf['use_layer_norm'],
        img_height=data_conf['img_height'],
        img_width=data_conf['img_width']
    )

    # 5. CARGAR LOS PESOS
    # Tu train.py guarda esto bajo la llave 'model_state_dict'
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval() # Poner en modo evaluación

    # 6. APLICAR CUANTIZACIÓN DINÁMICA (EL TRUCO DE MAGIA)
    print("Aplicando cuantización dinámica...")
    quantized_model = torch.quantization.quantize_dynamic(
        model, 
        {torch.nn.LSTM, torch.nn.Linear},  # Capas a optimizar
        dtype=torch.qint8
    )

    # 7. PREPARAR EL TENSOR DE PRUEBA (SHAPE REAL)
    # Shape: (Batch, Seq_Len, Channels, Height, Width)
    # Batch = 1 (una sola inferencia)
    seq_len = data_conf['input_steps']
    channels = model_conf['input_dim']
    h = data_conf['img_height']
    w = data_conf['img_width']
    
    print(f"Creando input de prueba con shape: (1, {seq_len}, {channels}, {h}, {w})")
    input_tensor = torch.randn(1, seq_len, channels, h, w)

    # 8. MEDIR TIEMPOS
    print("Corriendo inferencia de prueba...")
    
    # Calentamiento (opcional, para cargar librerías en memoria)
    with torch.no_grad():
        _ = quantized_model(input_tensor)

    start = time.time()
    with torch.no_grad():
        output = quantized_model(input_tensor)
    end = time.time()
    
    duration = end - start
    print("-" * 30)
    print(f"¡ÉXITO!")
    print(f"Tiempo de inferencia en CPU: {duration:.4f} segundos")
    print("-" * 30)

    # Guardar modelo optimizado si fue rápido
    if duration < 15.0:
        output_name = "modelo_cpu_optimizado.pth"
        # Nota: Guardamos solo el state_dict del cuantizado
        torch.save(quantized_model.state_dict(), output_name)
        print(f"Modelo optimizado guardado como: {output_name}")
    else:
        print("El modelo sigue siendo lento para CPU (>15s).")

if __name__ == "__main__":
    main()