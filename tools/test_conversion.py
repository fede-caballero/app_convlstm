import os
import shutil
import glob
import subprocess
import logging
import argparse

# --- Configuración del Logging para ver mensajes claros ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_mdv_to_nc(mdv_filepath: str, final_output_dir: str, params_path: str):
    """
    Ejecuta Mdv2NetCDF en un directorio temporal, encuentra el archivo .nc,
    lo renombra al formato YYYYMMDDHHMMSS.nc (para un ordenamiento correcto)
    y lo mueve al directorio de salida final, limpiando los archivos temporales.
    """
    mdv_filename = os.path.basename(mdv_filepath)
    logging.info(f"Iniciando conversión de {mdv_filename}...")

    # --- 1. Crear un entorno de trabajo temporal y aislado ---
    # Usamos una ruta relativa para que funcione en cualquier máquina
    temp_work_dir = "./temp_conversion_workspace"
    if os.path.exists(temp_work_dir):
        shutil.rmtree(temp_work_dir)
    os.makedirs(temp_work_dir)

    original_dir = os.getcwd()
    os.chdir(temp_work_dir)

    try:
        # --- 2. Ejecutar el comando validado ---
        # Usamos rutas absolutas para los archivos para evitar ambigüedades
        command = [
            "Mdv2NetCDF",
            "-params", os.path.abspath(params_path),
            "-f", os.path.abspath(mdv_filepath)
        ]
        
        logging.info(f"Ejecutando comando: {' '.join(command)}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)

        # --- 3. Encontrar, renombrar y mover el archivo de salida ---
        search_path = os.path.join(os.getcwd(), "netCDF", "*.nc")
        nc_files_found = glob.glob(search_path)

        if not nc_files_found:
            logging.error("Conversión reportó éxito, pero no se encontró ningún archivo .nc.")
            return False

        created_nc_path = nc_files_found[0]
        base_nc_name = os.path.basename(created_nc_path)
        
        try:
            parts = base_nc_name.replace('ncfdata', '').replace('.nc', '').split('_')
            final_filename = f"{parts[0]}{parts[1]}.nc"
        except IndexError:
            logging.warning(f"No se pudo parsear el nombre '{base_nc_name}'. Usando nombre original.")
            final_filename = base_nc_name

        final_nc_path = os.path.join(os.path.abspath(final_output_dir), final_filename)
        
        logging.info(f"Moviendo y renombrando '{base_nc_name}' a '{final_nc_path}'")
        shutil.move(created_nc_path, final_nc_path)
        
        logging.info("Conversión y limpieza completadas exitosamente.")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.error(f"Falló la conversión de {mdv_filename}.")
        if isinstance(e, subprocess.CalledProcessError):
            logging.error(f"Error de LROSE: {e.stderr}")
        else:
            logging.error(f"Error de sistema: {e}")
        return False
    
    finally:
        # --- 4. Limpieza ---
        os.chdir(original_dir)
        if os.path.exists(temp_work_dir):
            shutil.rmtree(temp_work_dir)

# --- Bloque principal para ejecutar el script desde la terminal ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script de prueba para la conversión de un archivo MDV a NetCDF usando LROSE.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-f", "--file", 
        required=True, 
        help="Ruta al archivo MDV de entrada que quieres convertir."
    )
    parser.add_argument(
        "-o", "--output_dir", 
        required=True, 
        help="Directorio donde se guardará el archivo NetCDF convertido."
    )
    parser.add_argument(
        "-p", "--params", 
        required=True, 
        help="Ruta a tu archivo Mdv2NetCDF.params."
    )
    args = parser.parse_args()

    # Crear el directorio de salida si no existe
    os.makedirs(args.output_dir, exist_ok=True)

    logging.info("--- INICIANDO PRUEBA DE CONVERSIÓN LOCAL ---")
    
    success = convert_mdv_to_nc(args.file, args.output_dir, args.params)

    if success:
        print("\n✅ --- PRUEBA EXITOSA --- ✅")
        print(f"Revisa el archivo convertido en el directorio: {os.path.abspath(args.output_dir)}")
    else:
        print("\n❌ --- PRUEBA FALLIDA --- ❌")
        print("Revisa los mensajes de error de arriba para más detalles.")
