import os
import sys
import time
import glob
import shutil
import torch
import torch.nn.functional as F
import numpy as np
import subprocess
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import xarray as xr

# --- CONFIGURACIÓN ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

# --- CONFIGURACIÓN LROSE ---
LROSE_BIN = "/usr/local/lrose/bin"
MDV2NETCDF = os.path.join(LROSE_BIN, "Mdv2NetCDF")
PARAMS_FILE = os.path.join(project_root, "backend", "lrose_params", "Mdv2NetCDF.params")

from backend.model.architecture import ConvLSTM3D_Enhanced

# --- PARÁMETROS DEL MODELO (Igual que config.py) ---
MIN_DBZ = -29.0
MAX_DBZ = 65.0
IMG_SIZE_MODEL = 250
IMG_SIZE_ORIG = 500
PRED_STEPS = 7

# --- VISUALIZACIÓN SIMPLIFICADA (SIN CARTOPY) ---
def save_titan_image(composite_data_2d, output_image_path):
    try:
        # Configuración de Colores TITAN (Copiado EXACTO de pipeline_worker.py)
        titan_bounds = [5, 10, 20, 30, 35, 36, 39, 42, 45, 48, 51, 54, 57, 60, 65, 70, 80]
        titan_colors = [
            '#483d8b', # 5-10   (DarkSlateBlue)
            '#005a00', # 10-20  (DarkGreen)
            '#007000', # 20-30  (Green)
            '#087fdb', # 30-35  (MediumBlue)
            '#1c47e8', # 35-36  (Blue)
            '#6e0dc6', # 36-39  (Purple)
            '#c80f86', # 39-42  (Magenta)
            '#c06487', # 42-45  (PaleVioletRed)
            '#d2883b', # 45-48  (Peru)
            '#fac431', # 48-51  (Goldenrod)
            '#fefa03', # 51-54  (Yellow)
            '#fe9a58', # 54-57  (SandyBrown)
            '#fe5f05', # 57-60  (OrangeRed)
            '#fd341c', # 60-65  (Red)
            '#bebebe', # 65-70  (Gray)
            '#d3d3d3'  # 70-80  (LightGray)
        ]
        
        cmap = ListedColormap(titan_colors)
        cmap.set_under('none') 
        norm = BoundaryNorm(titan_bounds, cmap.N)
        
        fig = plt.figure(figsize=(10, 10), dpi=150)
        ax = fig.add_subplot(1, 1, 1)
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.set_axis_off()
        
        # Niveles para contourf (suavizado)
        # Importante: Deben coincidir con los bounds o cubrir el rango completo para que se vean todos los colores
        levels = titan_bounds 
        
        h, w = composite_data_2d.shape
        x = np.arange(w)
        y = np.arange(h)
        
        # Usamos contourf con antialiasing
        ax.contourf(x, y, composite_data_2d, levels=levels, cmap=cmap, norm=norm, extend='max', antialiased=True)
        
        plt.tight_layout(pad=0)
        plt.savefig(output_image_path, dpi=300, transparent=True, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        return True
    except Exception as e:
        print(f"Error generando imagen: {e}")
        return False

def generar_imagen_simple(nc_file_path, output_image_path):
    # Wrapper for backward compatibility or testing individual NCs
    try:
        ds = xr.open_dataset(nc_file_path, decode_times=False)
        if 'DBZ' in ds:
            dbz_data = ds['DBZ'].squeeze().values
        elif 'dbz' in ds:
            dbz_data = ds['dbz'].values
        else:
            var_name = list(ds.data_vars)[0]
            dbz_data = ds[var_name].values
        ds.close()

        if dbz_data.ndim == 3:
            composite_data_2d = np.nanmax(dbz_data, axis=0)
        elif dbz_data.ndim == 2:
            composite_data_2d = dbz_data
        else:
            return False
            
        return save_titan_image(composite_data_2d, output_image_path)
    except Exception as e:
        print(f"Error wrapper imagen: {e}")
        return False

def convert_mdv_to_nc(mdv_path, output_dir, verbose=False):
    if not os.path.exists(MDV2NETCDF):
        print(f"ERROR CRÍTICO: No se encontró {MDV2NETCDF}.")
        return None
    # Use -out_dir and -out_name to ensure predictable output
    # Mdv2NetCDF usually creates year/month/day subdirectories OR flat depending on params.
    # We force 'test_nc' prefix to handle simple case, but glob handles finding whatever is made.
    cmd = [MDV2NETCDF, "-params", PARAMS_FILE, "-f", mdv_path, "-out_dir", output_dir]
    
    try:
        # If verbose, allow output to console
        stdout = None if verbose else subprocess.DEVNULL
        stderr = None if verbose else subprocess.DEVNULL
        
        subprocess.run(cmd, check=True, stdout=stdout, stderr=stderr)
        
        # 1. Search in requested output_dir
        generated = glob.glob(os.path.join(output_dir, "**", "*.nc"), recursive=True)
        
        # 2. Fallback: Search in CWD/netCDF (Default LROSE behavior if ignoring arg)
        if not generated:
            cwd_netcdf = os.path.join(os.getcwd(), "netCDF")
            if os.path.exists(cwd_netcdf):
                 generated = glob.glob(os.path.join(cwd_netcdf, "**", "*.nc"), recursive=True)

        if generated:
            # Filter by modification time is safest if multiple exist, but here we expect just one per call ideally.
            generated.sort(key=os.path.getmtime)
            last_file = generated[-1]
            
            # Move to output_dir if it's not there (Clean up)
            if not last_file.startswith(output_dir):
                dest_name = os.path.basename(last_file)
                dest_path = os.path.join(output_dir, dest_name)
                shutil.move(last_file, dest_path)
                return dest_path
                
            return last_file
        
        if verbose: print(f"  ⚠ No se encontraron .nc en {output_dir} ni en ./netCDF")
        return None
    except Exception as e:
        print(f" Error convirtiendo {mdv_path}: {e}")
        return None

def load_cpu_model(checkpoint_path):
    print(f"Cargando {os.path.basename(checkpoint_path)}...")
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # 1. Caso: Checkpoint Original (Con Configuración Completa)
    if 'config' in checkpoint:
        print("✅ Configuración encontrada en checkpoint. Usando parámetros exactos.")
        config = checkpoint['config']
        model_conf = config['model']
        data_conf = config['data']
        
        model = ConvLSTM3D_Enhanced(
            input_dim=model_conf['input_dim'],
            hidden_dims=model_conf['hidden_dims'],
            kernel_sizes=model_conf['kernel_sizes'],
            num_layers=model_conf['num_layers'],
            pred_steps=data_conf.get('prediction_steps', PRED_STEPS), # Fallback safety
            use_layer_norm=model_conf['use_layer_norm'],
            img_height=data_conf['img_height'],
            img_width=data_conf['img_width']
        )
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        print("-> Modelo FP32 Original cargado (Sin cuantización extra).")
        return model

    # 2. Caso: Modelo Optimizado (Solo State Dict, configuración Hardcoded)
    else:
        print("⚠ Checkpoint optimizado (sin config). Usando parámetros hardcoded + Cuantización.")
        model = ConvLSTM3D_Enhanced(
            input_dim=1,
            hidden_dims=[128, 128, 128],
            kernel_sizes=[(3, 3), (3, 3), (3, 3)],
            num_layers=3,
            pred_steps=PRED_STEPS,
            use_layer_norm=True,
            img_height=IMG_SIZE_MODEL,
            img_width=IMG_SIZE_MODEL # 250
        )
        
        quantized_model = torch.quantization.quantize_dynamic(
            model, {torch.nn.LSTM, torch.nn.Linear}, dtype=torch.qint8
        )
        
        # Cargar state_dict directamente al cuantizado
        # (Esto asume que el archivo .pth guardado ES el state dict cuantizado)
        try:
            quantized_model.load_state_dict(checkpoint)
        except Exception as e:
            print(f"Error cargando state_dict cuantizado: {e}")
            # Fallback: Maybe it was wrapped?
            if 'model_state_dict' in checkpoint:
                quantized_model.load_state_dict(checkpoint['model_state_dict'])
        
        quantized_model.eval()
        return quantized_model

def run_test(mdv_folder, model_path):
    # 1. MDVs
    mdv_files = sorted(glob.glob(os.path.join(mdv_folder, "*.mdv")))
    if len(mdv_files) < 8:
        print(f"⚠ Se requieren 8 archivos MDV. Encontrados: {len(mdv_files)}")
    
    input_mdvs = mdv_files[-8:]
    print(f"Procesando {len(input_mdvs)} archivos MDV...")
    
    # 2. Convertir
    temp_nc_dir = os.path.join(current_dir, "temp_nc")
    os.makedirs(temp_nc_dir, exist_ok=True)
    
    print(f"PARAMS_FILE esperado: {PARAMS_FILE}")
    if not os.path.exists(PARAMS_FILE):
        print("ERROR CRÍTICO: No se encontró el archivo de parámetros PARAMS_FILE.")
    
    nc_files = []
    print("Convirtiendo MDV -> NetCDF (LROSE)...")
    start_conv = time.time()
    for mdv in input_mdvs:
        print(f"  > Procesando: {os.path.basename(mdv)}")
        # Allow stderr/stdout for debug
        nc_path = convert_mdv_to_nc(mdv, temp_nc_dir, verbose=True)
        if nc_path:
            nc_files.append(nc_path)
        else:
            print(f"  ⚠ Fallo al convertir {os.path.basename(mdv)}")
            
    print(f"Conversión completada en {time.time() - start_conv:.2f}s")
    print(f"Archivos NetCDF generados: {len(nc_files)}")

    if len(nc_files) == 0:
        print("ERROR CRÍTICO: No se generaron archivos NetCDF validos. Abortando.")
        return

    # 3. Preparar Tensor (Preprocessing + Downsampling)
    print("Preparando tensor de entrada...")
    tensors = []
    SKIP_LEVELS = 2 # Ignorar los 2 niveles más bajos (clutter)

    for i, nc in enumerate(nc_files):
        ds = xr.open_dataset(nc, decode_times=False) # Important: decode_times=False
        if 'DBZ' in ds:
            data = ds['DBZ'].values
        elif 'dbz' in ds:
            data = ds['dbz'].values
        else:
            var_name = list(ds.data_vars)[0]
            data = ds[var_name].values
        
        # DEBUG: Raw Stats (Full Volume)
        print(f"  [{i}] Raw Vol Stats: Min={np.nanmin(data):.2f}, Max={np.nanmax(data):.2f}, Mean={np.nanmean(data):.2f}")
        
        # Proyeccion Maxima Z (Strictly matching train.py: Max over all Z)
        if data.ndim == 3:
            # (Z, Y, X)
            data = np.nanmax(data, axis=0) # 3D -> 2D
        elif data.ndim > 3:
             # Case (Time, Z, Y, X)
             if data.shape[0] == 1:
                 data = data[0]
             if data.ndim == 3:
                 data = np.nanmax(data, axis=0)
        
        # Replace NaNs
        data = np.nan_to_num(data, nan=MIN_DBZ)
        
        # Clip values to range (Safety)
        data = np.clip(data, MIN_DBZ, MAX_DBZ)
        
        # Normalize
        data = (data - MIN_DBZ) / (MAX_DBZ - MIN_DBZ)
        
        # DEBUG: Norm Stats (2D Composite)
        print(f"  [{i}] 2D Norm Stats: Min={np.min(data):.2f}, Max={np.max(data):.2f}, Mean={np.mean(data):.2f}")
        
        # To Tensor
        t_data = torch.from_numpy(data).float() # (H_orig, W_orig)
        
        # Add Channel dim
        t_data = t_data.unsqueeze(0) # (1, H, W)
        
        # DOWNSAMPLING (500 -> 250)
        # Importante: Interpolar espera (Batch, Channel, H, W) -> (1, 1, H, W)
        # t_data shape now: (1, 500, 500). Unsqueeze(0) -> (1, 1, 500, 500)
        if t_data.shape[1] != IMG_SIZE_MODEL or t_data.shape[2] != IMG_SIZE_MODEL:
             t_data = F.interpolate(
                t_data.unsqueeze(0), 
                size=(IMG_SIZE_MODEL, IMG_SIZE_MODEL), 
                mode='bilinear', 
                align_corners=False
            ).squeeze(0) # Back to (1, 250, 250)
            
        tensors.append(t_data)
        ds.close()
        
    while len(tensors) < 8:
         tensors.append(torch.randn(1, IMG_SIZE_MODEL, IMG_SIZE_MODEL))
    
    # Stack: (Batch=1, Time=8, Channel=1, H, W)
    input_tensor = torch.stack(tensors).unsqueeze(0) 
    
    # 4. Inferencia
    print("Ejecutando Inferencia CPU...")
    model = load_cpu_model(model_path)
    
    start_inf = time.time()
    with torch.no_grad():
        output = model(input_tensor)
    duration = time.time() - start_inf
    print(f"✅ Inferencia completada en: {duration:.4f} segundos")
    
    # 5. Generar Imágenes (Postprocessing + Upsampling)
    print(f"Generando {PRED_STEPS} imágenes de salida (Vector-like)...")
    
    for i in range(PRED_STEPS):
        pred_tensor = output[0, i, 0] # (250, 250)
        
        # UPSAMPLING (250 -> 500)
        pred_upscaled = F.interpolate(
            pred_tensor.unsqueeze(0).unsqueeze(0),
            size=(IMG_SIZE_ORIG, IMG_SIZE_ORIG),
            mode='bilinear',
            align_corners=False
        ).squeeze()
        
        pred_data = pred_upscaled.numpy()
        
        # Denormalize
        pred_dbz = pred_data * (MAX_DBZ - MIN_DBZ) + MIN_DBZ
        
        # DEBUG: Check Max Value
        max_val = np.max(pred_dbz)
        if i == 0: print(f"  [T+{i+1}] Max Pred DBZ: {max_val:.2f}")
        
        filename = f"pred_t{i+1}.png"
        out_png = os.path.join(current_dir, filename)
        
        # Pass numpy array directly to plotter
        if save_titan_image(pred_dbz, out_png):
            print(f"  -> {filename}")
    
    if os.path.exists(temp_nc_dir):
        shutil.rmtree(temp_nc_dir)
        
    # Clean up local netCDF folder artifacts
    cwd_netcdf = os.path.join(os.getcwd(), "netCDF")
    if os.path.exists(cwd_netcdf):
        # Clean up _latest_data_info... inside
        for f in glob.glob(os.path.join(cwd_netcdf, "_latest_data_info*")):
             os.remove(f)
             
        # Optional: remove folder if empty? 
        # Usually better to leave it or remove everything inside.
        # Let's remove everything inside just to be clean for next run.
        for f in glob.glob(os.path.join(cwd_netcdf, "*")):
            try:
                if os.path.isfile(f): os.remove(f)
            except: pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 test_local_pipeline.py <carpeta_con_mdvs> <ruta_modelo_optimizado.pth>")
    else:
        run_test(sys.argv[1], sys.argv[2])
