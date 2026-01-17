import os
import argparse
import glob
import numpy as np
import torch
import xarray as xr
from datetime import datetime, timedelta, timezone
from netCDF4 import Dataset as NCDataset
import sys
import pyproj
import re

# Append project root to path if needed to find backend modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.model.architecture import ConvLSTM3D_Enhanced
except ImportError:
    print("Error: Could not import backend.model.architecture. Make sure you are in the project root or adjust sys.path")
    sys.exit(1)

# --- Configuration for San Rafael Radar ---
DATA_CONFIG = {
    'min_dbz': -29.0, 
    'max_dbz': 65.0, 
    'variable_name': 'DBZ',
    'prediction_interval_minutes': 3.5, 
    'sensor_latitude': -34.6479988098145,
    'sensor_longitude': -68.0169982910156,
    'earth_radius_m': 6378137.0,
    'radar_name': 'SAN_RAFAEL_PRED',
    'institution_name': 'UM',
    'data_source_name': 'ConvLSTM Model Prediction',
    # 3D Settings (Single Level - No Extrusion)
    'num_levels': 1,
    'level_start_km': 1.0,
    'level_step_km': 1.0
}

def extract_timestamp(filename):
    """
    Extracts timestamp from filename using regex.
    Supports: YYYYMMDD_HHMMSS or YYYYMMDDHHMMSS
    """
    # Regex for YYYYMMDD_HHMMSS or YYYYMMDDHHMMSS
    pattern = r"(\d{8})_?(\d{6})"
    match = re.search(pattern, os.path.basename(filename))
    
    if match:
        date_part, time_part = match.groups()
        dt_str = f"{date_part}{time_part}"
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
            
    print(f"Warning: Could not parse time from {filename}. Using current time.")
    return datetime.now(timezone.utc)

def preprocess_input(nc_files, img_height=250, img_width=250):
    frames = []
    print(f"Loading {len(nc_files)} files...")
    for p in nc_files:
        with xr.open_dataset(p, mask_and_scale=True, decode_times=False) as ds:
            # Fallback for variable name
            var_name = 'DBZ' if 'DBZ' in ds else list(ds.data_vars)[0]
            data = ds[var_name].values
            
            # Convert to Tensor
            data = torch.from_numpy(data).float()
            
            # 1. Handle NaNs IMMEDIATELY
            data = torch.nan_to_num(data, nan=-29.0)
            
            # 2. Dimension Reduction (Max Projection if 3D input)
            while data.ndim > 2:
                if data.shape[0] == 1:
                    data = data.squeeze(0)
                else:
                    data = torch.max(data, dim=0)[0]
            
            # Ensure (1, H, W)
            if data.ndim == 2:
                data = data.unsqueeze(0)
                
            # 3. Clip & Normalize
            data = torch.clamp(data, min=-29.0, max=65.0)
            data = (data - (-29.0)) / (65.0 - (-29.0))
            
            # 4. Resize if needed
            if data.shape[1] != img_height or data.shape[2] != img_width:
                data = torch.nn.functional.interpolate(
                    data.unsqueeze(0),
                    size=(img_height, img_width),
                    mode='bilinear',
                    align_corners=False
                ).squeeze(0)
                
            frames.append(data)
            
    # Stack: (Seq, C, H, W) -> (B, Seq, C, H, W)
    input_tensor = torch.stack(frames, dim=0).unsqueeze(0)
    return input_tensor

def save_prediction_as_netcdf(output_dir, pred_sequence_cleaned, data_cfg, start_datetime):
    """
    Saves predictions as NetCDF with proper CF metadata.
    Single vertical level (CAPPI/Max).
    """
    num_pred_steps, num_y, num_x = pred_sequence_cleaned.shape
    num_z = 1 # Force 1 level
    
    # --- Grid Preparation ---
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    
    # Single Altitude Level
    z_coords = np.array([data_cfg['level_start_km']], dtype=np.float32)

    proj = pyproj.Proj(
        proj="aeqd", 
        lon_0=data_cfg['sensor_longitude'], 
        lat_0=data_cfg['sensor_latitude'], 
        R=data_cfg['earth_radius_m']
    )
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    os.makedirs(output_dir, exist_ok=True)

    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * data_cfg['prediction_interval_minutes']
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        
        file_ts = forecast_dt_utc.strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(output_dir, f"{file_ts}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            # --- Global Attributes ---
            ds_out.Conventions = "CF-1.6"
            ds_out.title = f"{data_cfg['radar_name']} - Forecast t+{lead_time_minutes}min"
            ds_out.institution = data_cfg['institution_name']
            ds_out.source = data_cfg['data_source_name']
            ds_out.history = f"Created {datetime.now(timezone.utc).isoformat()} by ConvLSTM script."
            ds_out.comment = f"Forecast 2D (Max Projection). Lead time: {lead_time_minutes} min."

            # --- Dimensions ---
            ds_out.createDimension('time', None)
            ds_out.createDimension('bounds', 2)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

            # --- Variables ---
            time_value = (forecast_dt_utc.replace(tzinfo=timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
            time_v = ds_out.createVariable('time', 'f8', ('time',))
            time_v.standard_name = "time"; time_v.axis = "T"
            time_v.units = "seconds since 1970-01-01T00:00:00Z"
            time_v[:] = [time_value]

            x_v = ds_out.createVariable('longitude', 'f4', ('longitude',))
            x_v.standard_name = "projection_x_coordinate"; x_v.units = "km"; x_v.axis = "X"
            x_v[:] = x_coords

            y_v = ds_out.createVariable('latitude', 'f4', ('latitude',))
            y_v.standard_name = "projection_y_coordinate"; y_v.units = "km"; y_v.axis = "Y"
            y_v[:] = y_coords

            z_v = ds_out.createVariable('altitude', 'f4', ('altitude',))
            z_v.standard_name = "altitude"; z_v.units = "km"; z_v.axis = "Z"; z_v.positive = "up"
            z_v[:] = z_coords

            lat0_v = ds_out.createVariable('lat0', 'f4', ('latitude', 'longitude',))
            lat0_v.standard_name = "latitude"; lat0_v.units = "degrees_north"
            lat0_v[:] = lat0_grid

            lon0_v = ds_out.createVariable('lon0', 'f4', ('latitude', 'longitude',))
            lon0_v.standard_name = "longitude"; lon0_v.units = "degrees_east"
            lon0_v[:] = lon0_grid

            gm_v = ds_out.createVariable('grid_mapping_0', 'i4')
            gm_v.grid_mapping_name = "azimuthal_equidistant"
            gm_v.longitude_of_projection_origin = data_cfg['sensor_longitude']
            gm_v.latitude_of_projection_origin = data_cfg['sensor_latitude']
            gm_v.false_easting = 0.0; gm_v.false_northing = 0.0
            gm_v.earth_radius = data_cfg['earth_radius_m']

            # --- Data Variable (Single Level) ---
            fill_value_float = np.float32(-999.0)
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=fill_value_float)
            dbz_v.units = "dBZ"; dbz_v.standard_name = "reflectivity"
            dbz_v.grid_mapping = "grid_mapping_0"
            dbz_v.coordinates = "lat0 lon0"
            
            # Get 2D frame
            pred_2d = pred_sequence_cleaned[i] # (500, 500)
            
            # Shape (1, 1, Y, X)
            pred_final = pred_2d[np.newaxis, np.newaxis, :, :]
            
            data_final = np.nan_to_num(pred_final, nan=fill_value_float)
            
            dbz_v[:] = data_final

        print(f"Saved: {output_filename}")

def main():
    parser = argparse.ArgumentParser(description="Run ConvLSTM Inference (Standalone)")
    parser.add_argument('--input_dir', type=str, required=True, help="Folder containing .nc files")
    parser.add_argument('--model_path', type=str, required=True, help="Path to .pth checkpoint")
    parser.add_argument('--output_dir', type=str, default='predictions', help="Output folder")
    parser.add_argument('--seq_len', type=int, default=8, help="Input sequence length")
    args = parser.parse_args()

    # 1. Setup Model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = ConvLSTM3D_Enhanced(
        input_dim=1,
        hidden_dims=[128, 128, 128],
        kernel_sizes=[(3,3), (3,3), (3,3)],
        num_layers=3,
        pred_steps=7,
        use_layer_norm=True,
        img_height=250,
        img_width=250
    ).to(device)
    
    # 2. Load Weights
    print(f"Loading model from {args.model_path}...")
    checkpoint = torch.load(args.model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # 3. Find Files
    files = sorted(glob.glob(os.path.join(args.input_dir, "*.nc")))
    if len(files) < args.seq_len:
        print(f"Not enough files. Need {args.seq_len}, found {len(files)}.")
        return
    
    input_files = files[:args.seq_len]
    start_dt = extract_timestamp(input_files[-1]) # Use last file as t0
    print(f"Prediction base time (t0): {start_dt}")

    # 4. Preprocess & Inference
    with torch.no_grad():
        input_tensor = preprocess_input(input_files).to(device)
        print("Running inference...")
        output = model(input_tensor)
        
        # Upsampling
        b, t, c, h, w = output.shape
        output = output.view(b*t, c, h, w)
        output = torch.nn.functional.interpolate(output, size=(500, 500), mode='bicubic', align_corners=False)
        output = output.view(b, t, c, 500, 500)
        
        # Denormalize
        output_np = output.cpu().numpy()
        output_dbz = output_np * (DATA_CONFIG['max_dbz'] - DATA_CONFIG['min_dbz']) + DATA_CONFIG['min_dbz']
        output_dbz = np.clip(output_dbz, DATA_CONFIG['min_dbz'], DATA_CONFIG['max_dbz'])
        
        # Get Clean 2D Sequence (Time, Y, X)
        pred_clean = output_dbz[0, :, 0, :, :]
        
        # 5. Save (Pseudo-3D)
        save_prediction_as_netcdf(
            output_dir=args.output_dir, 
            pred_sequence_cleaned=pred_clean, 
            data_cfg=DATA_CONFIG, 
            start_datetime=start_dt
        )

if __name__ == "__main__":
    main()
