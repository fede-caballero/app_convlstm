
import os
import logging
import numpy as np
import xarray as xr
import pyart
import matplotlib.pyplot as plt

# --- Configuración del Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

import cartopy.crs as ccrs

def generar_imagen_desde_nc(nc_file_path: str, output_image_path: str, skip_levels: int = 2):
    """
    Genera una imagen de reflectividad compuesta sobre un mapa a partir de un archivo NetCDF.
    """
    try:
        logging.info(f"Generando imagen para: {os.path.basename(nc_file_path)}")
        
        ds = xr.open_dataset(nc_file_path, mask_and_scale=True, decode_times=False)

        lon_name = 'longitude' if 'longitude' in ds.coords else 'x0'
        lat_name = 'latitude' if 'latitude' in ds.coords else 'y0'
        alt_name = 'altitude' if 'altitude' in ds.coords else 'z0'
        
        x = ds[lon_name].values
        y = ds[lat_name].values
        z = ds[alt_name].values
        dbz_data = ds['DBZ'].squeeze().values

        # --- 1. Crear el composite omitiendo los primeros niveles ---
        if dbz_data.ndim == 3 and dbz_data.shape[0] > skip_levels:
            composite_data_2d = np.nanmax(dbz_data[skip_levels:, :, :], axis=0)
        else:
            composite_data_2d = np.nanmax(dbz_data, axis=0)

        # --- 2. Obtener la información de la proyección ---
        # Usamos los metadatos del archivo NetCDF para definir la proyección del mapa
        proj_info = ds['grid_mapping_0'].attrs
        lon_0 = proj_info['longitude_of_projection_origin']
        lat_0 = proj_info['latitude_of_projection_origin']
        # La proyección de los datos es Azimutal Equidistante (aeqd)
        projection = ccrs.AzimuthalEquidistant(central_longitude=lon_0, central_latitude=lat_0)

        # --- 3. Creación del gráfico final con mapa ---
        logging.info("Generando gráfico final con mapa...")
        fig = plt.figure(figsize=(12, 12))
        ax = fig.add_subplot(1, 1, 1, projection=projection)

        # Definir la extensión de los datos en metros (Py-ART usa km, imshow necesita metros para la proyección)
        x_min, x_max = x.min() * 1000, x.max() * 1000
        y_min, y_max = y.min() * 1000, y.max() * 1000
        extent = (x_min, x_max, y_min, y_max)

        # Dibujar la imagen de reflectividad en el eje del mapa
        im = ax.imshow(composite_data_2d, cmap='LangRainbow12', origin='lower', 
                       vmin=0, vmax=70, extent=extent)

        # Añadir características del mapa
        ax.coastlines(resolution='10m', color='black', linewidth=0.5)
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

        fig.colorbar(im, ax=ax, label="Reflectividad (dBZ)", shrink=0.7)
        ax.set_title(f"Reflectividad Compuesta - {os.path.basename(nc_file_path)}")
        
        plt.tight_layout()
        plt.savefig(output_image_path, dpi=150)
        plt.close(fig)

        logging.info(f"  -> Imagen final guardada en: {output_image_path}")
        return True

    except Exception as e:
        logging.error(f"No se pudo generar la imagen para {nc_file_path}: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # --- MODIFICA ESTAS LÍNEAS ---
    # Reemplaza con la ruta a tu archivo NetCDF de predicción
    INPUT_NC_FILE = "/home/f-caballero/Desktop/Pruebas_automatizacion/processing_workspace/netcdf_predictions/predictions/20080101_182757.nc" 
    # Nombre del archivo de imagen de salida
    OUTPUT_PNG_FILE = "test_output.png"
    # -----------------------------

    # Obtener la ruta del directorio del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_NC_FILE)
    output_path = os.path.join(script_dir, OUTPUT_PNG_FILE)

    if not os.path.exists(input_path):
        logging.error(f"El archivo de entrada no se encontró en: {input_path}")
        logging.error("Por favor, asegúrate de que el archivo exista y la variable INPUT_NC_FILE sea correcta.")
    else:
        logging.info("--- Iniciando prueba de generación de imagen ---")
        success = generar_imagen_desde_nc(input_path, output_path, skip_levels=2)
        if success:
            logging.info("--- Prueba finalizada con éxito ---")
        else:
            logging.error("--- La prueba falló. Revisa los logs de error. ---")

