# -*- coding: utf-8 -*-
"""
Script actualizado para convertir un archivo MDV CARTESIANO a una imagen PNG
de forma automatizada utilizando Py-ART y Matplotlib.
"""

import matplotlib
# Establecer el backend de Matplotlib a 'Agg' para uso en servidor (no interactivo).
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pyart
import warnings

# Suprimir advertencias comunes durante la lectura de archivos.
warnings.filterwarnings("ignore", category=UserWarning)

def cartesian_mdv_to_image(mdv_input_path, png_output_path, field='reflectivity', level=0):
    """
    Lee un archivo MDV que contiene datos en una rejilla cartesiana, genera un
    gráfico de un nivel de altura específico y lo guarda como un archivo PNG.

    Args:
        mdv_input_path (str): Ruta al archivo MDV cartesiano de entrada.
        png_output_path (str): Ruta donde se guardará la imagen PNG de salida.
        field (str): Nombre del campo a visualizar (ej. 'reflectivity').
        level (int): Índice del nivel vertical (eje Z) a visualizar.
    """
    try:
        # Paso 1: Leer el archivo MDV cartesiano usando la función específica de Py-ART.
        # Esto devuelve un objeto 'Grid' en lugar de un objeto 'Radar'.
        print(f"Leyendo el archivo MDV cartesiano: {mdv_input_path}...")
        grid = pyart.io.read_grid_mdv(mdv_input_path)
        print("Lectura del archivo completada.")

        # Paso 2: Crear un objeto GridMapDisplay para la visualización de datos en rejilla.
        # Este objeto es el equivalente a RadarDisplay pero para datos cartesianos.
        display = pyart.graph.GridMapDisplay(grid)

        # Paso 3: Configurar la figura de Matplotlib.
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111)

        # Paso 4: Trazar el campo de datos del nivel especificado.
        # El método plot_grid se usa para visualizar un plano 2D de la rejilla 3D.
        print(f"Generando gráfico para el campo '{field}', nivel {level}...")
        display.plot_grid(
            field,
            level=level,
            ax=ax,
            vmin=-29,          # Valor mínimo para la escala de colores (dBZ)
            vmax=65,           # Valor máximo para la escala de colores (dBZ)
            cmap='NWSRef', # Una paleta de colores común en meteorología
            colorbar_label='Reflectividad (dBZ)'
        )
        
        # Opcional: Añadir un título al gráfico.
        ax.set_title(f'Visualización Cartesiana - Nivel {level}')

        # Paso 5: Guardar la figura en un archivo PNG.
        print(f"Guardando imagen en: {png_output_path}...")
        plt.savefig(png_output_path, dpi=150, bbox_inches='tight')
        print("Imagen guardada con éxito.")

    except Exception as e:
        print(f"Ocurrió un error: {e}")
    
    finally:
        # Paso 6: Cerrar la figura para liberar memoria.
        if 'fig' in locals():
            plt.close(fig)

# --- Ejemplo de uso ---
if __name__ == '__main__':
    # Deberás reemplazar esta ruta con la de tu propio archivo MDV cartesiano.
    # Py-ART no incluye un archivo de prueba MDV cartesiano por defecto.
    mdv_file_path = "/home/f-caballero/UM/TIF3/MDV_para_25_50050018/2007/20070205/222330.mdv"
    output_image_file = 'cartesian_reflectivity.png'
    
    print("Este script requiere un archivo MDV cartesiano real.")
    print(f"Por favor, edita el script y cambia 'mdv_file_path' a la ruta de tu archivo.")
    
    # Si tuvieras un archivo, la llamada sería así:
    cartesian_mdv_to_image(mdv_file_path, output_image_file)
