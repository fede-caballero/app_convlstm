import os
import glob
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from netCDF4 import Dataset

def visualize_folder(input_dir, output_gif='prediction.gif', variable='DBZ'):
    # Find files
    files = sorted(glob.glob(os.path.join(input_dir, "*.nc")))
    if not files:
        print(f"No .nc files found in {input_dir}")
        return

    print(f"Found {len(files)} files. Creating animation...")

    frames = []
    timestamps = []

    # Load data
    for f in files:
        try:
            with Dataset(f, 'r') as nc:
                # Shape is (time, altitude, lat, lon) -> (1, 1, 500, 500) or similar
                # We need to squeeze to (500, 500)
                data = nc.variables[variable][:]
                data = np.squeeze(data) 
                
                # If dimensions are still > 2, take the max over Z or first level
                if data.ndim > 2:
                    data = data[0, :, :] # Assume (Z, Y, X) -> Take Z=0
                
                # Replace invalid values for plotting
                fill_val = nc.variables[variable].getncattr('_FillValue')
                data = np.ma.masked_equal(data, fill_val)
                # Also mask values below threshold typically used for display
                data = np.ma.masked_less(data, -32.0) 
                
                frames.append(data)
                
                # Try simple filename timestamp parsing for label
                fname = os.path.basename(f)
                timestamps.append(fname)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not frames:
        print("No valid data loaded.")
        return

    # Setup Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Initial plot
    # Use a radar-like colormap (e.g., 'jet' or 'nipy_spectral')
    cmap = plt.get_cmap('nipy_spectral')
    im = ax.imshow(frames[0], origin='lower', cmap=cmap, vmin=-30, vmax=70)
    plt.colorbar(im, ax=ax, label='DBZ')
    
    title = ax.set_title(f"Reflectivity - {timestamps[0]}")

    def update(frame_idx):
        im.set_data(frames[frame_idx])
        title.set_text(f"Reflectivity - {timestamps[frame_idx]}")
        return [im, title]

    ani = animation.FuncAnimation(fig, update, frames=len(frames), interval=500, blit=True)
    
    # Save
    ani.save(output_gif, writer='pillow', fps=2)
    print(f"Animation saved to: {output_gif}")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize NetCDF Predictions")
    parser.add_argument('--input_dir', type=str, required=True, help="Folder with .nc files")
    parser.add_argument('--output', type=str, default='prediction.gif', help="Output GIF path")
    args = parser.parse_args()
    
    visualize_folder(args.input_dir, args.output)
