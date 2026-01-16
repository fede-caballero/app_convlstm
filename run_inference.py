import os
import argparse
import glob
import numpy as np
import torch
import xarray as xr
from datetime import datetime, timedelta
from netCDF4 import Dataset as NCDataset
import sys

# Append project root to path if needed to find backend modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.model.architecture import ConvLSTM3D_Enhanced
except ImportError:
    print("Error: Could not import backend.model.architecture. Make sure you are in the project root or adjust sys.path")
    # For standalone usage without the full repo, you could paste the model class here.
    sys.exit(1)

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
            
            # 1. Handle NaNs IMMEDIATELY (Same as training)
            data = torch.nan_to_num(data, nan=-29.0)
            
            # 2. Dimension Reduction (Max Projection)
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

def save_netcdf(output_path, data, ref_file):
    """
    Saves the prediction as a minimal NetCDF file.
    data: (1, 500, 500) numpy array (DBZ)
    ref_file: path to an input file to copy spatial metadata from
    """
    # Create dir
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with NCDataset(output_path, 'w', format='NETCDF4') as nc:
        # Dimensions (Simplified)
        nc.createDimension('y', 500)
        nc.createDimension('x', 500)
        nc.createDimension('time', 1)
        
        # Variables
        dbz = nc.createVariable('DBZ', 'f4', ('time', 'y', 'x'), fill_value=-999.0)
        dbz.units = 'dBZ'
        
        # Write Data
        dbz[0, :, :] = data[0]
        
    print(f"Saved: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Run ConvLSTM Inference")
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
        pred_steps=7, # Fixed for this model
        use_layer_norm=True,
        img_height=250,
        img_width=250
    ).to(device)
    
    # 2. Load Weights
    checkpoint = torch.load(args.model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    print("Model loaded.")

    # 3. Find Files
    files = sorted(glob.glob(os.path.join(args.input_dir, "*.nc")))
    if len(files) < args.seq_len:
        print(f"Not enough files. Need {args.seq_len}, found {len(files)}.")
        return
    
    # Take first sequence for testing
    input_files = files[:args.seq_len]
    
    # 4. Preprocess
    with torch.no_grad():
        input_tensor = preprocess_input(input_files).to(device)
        print(f"Input shape: {input_tensor.shape}") # (1, 8, 1, 250, 250)

        # 5. Inference
        print("Running inference...")
        output = model(input_tensor) # (1, 7, 1, 250, 250)
        
        # 6. Upsample to 500x500
        print("Upsampling...")
        b, t, c, h, w = output.shape
        output = output.view(b*t, c, h, w)
        output = torch.nn.functional.interpolate(output, size=(500, 500), mode='bicubic', align_corners=False)
        output = output.view(b, t, c, 500, 500)
        
        # 7. Denormalize
        output_np = output.cpu().numpy()
        output_dbz = output_np * (65.0 - (-29.0)) + (-29.0)
        output_dbz = np.clip(output_dbz, -29.0, 65.0)
        
        # 8. Save
        for t_step in range(output_dbz.shape[1]):
            frame_dbz = output_dbz[0, t_step] # (1, 500, 500)
            out_name = os.path.join(args.output_dir, f"pred_t+{t_step+1}.nc")
            save_netcdf(out_name, frame_dbz, input_files[-1])

if __name__ == "__main__":
    main()
