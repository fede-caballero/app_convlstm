# Guía de Despliegue y Ejecución del Backend

Este documento describe el proceso para desplegar y probar el backend del pipeline de predicción en una instancia de vast.ai.

## Prerrequisitos

1. **Imagen de Docker Actualizada**: Asegúrate de que la última versión de tu imagen (ej. frcaballero/lrose-pipeline:v1.2) esté construida y subida a Docker Hub.
2. **Enlace del Modelo**: Ten a mano el enlace de descarga directa de tu archivo best_convlstm_model.pth desde Google Drive.
3. **Datos de Prueba**: Prepara una carpeta en tu PC con 12 archivos .mdv para la prueba.
4. **Configuración SSH Local**: Asegúrate de que tu archivo ~/.ssh/config en tu PC esté configurado con el alias vast-a10.

## Proceso de Despliegue y Prueba

Este es el flujo completo desde alquilar la instancia hasta verificar el resultado.

### 1. Alquilar y Configurar la Instancia

- En el panel de vast.ai, alquila una nueva instancia usando tu última imagen de Docker (ej. v1.2).
- Asegúrate de configurar el "On-start Script" con el código para crear los directorios y descargar el modelo con gdown.
- Una vez que la instancia esté en estado "Running", obtén su nueva IP y Puerto.
- Actualiza tu archivo ~/.ssh/config local con la nueva IP y Puerto para el host vast-a10.

### 2. Iniciar el Backend

- Abre una terminal en tu PC.
- Conéctate a la instancia usando el alias configurado. La conexión ya incluirá el redireccionamiento de puertos.

```
ssh vast-a10
```

- Una vez dentro, el "On-start Script" ya habrá preparado el entorno. Inicia todos los servicios del backend:

```
cd /app && ./run.sh
```

- Deja esta terminal abierta. Mostrará los logs de la API y del worker en tiempo real.

### 3. Subir los Archivos MDV (Prueba Manual)

- Abre una segunda terminal en tu PC (no cierres la primera).
- Navega a la carpeta donde tienes tus archivos de prueba.
- Usa scp para subir los 12 archivos .mdv a la "bandeja de entrada" de la instancia:

```
# Reemplaza la ruta local si es necesario
scp ./*.mdv vast-a10:/app/mdv_inbox/
```

### 4. Monitorear y Verificar

1. **Monitorear Logs**: Observa la primera terminal (la que está conectada por SSH). Verás los mensajes del pipeline_worker a medida que detecta los archivos, los convierte, ejecuta el modelo y guarda los resultados.
2. **Verificar Estado con la API**: En el navegador de tu PC, visita la URL http://localhost:8080/api/status. Deberías ver cómo el estado cambia de "IDLE" a "PROCESSING" y luego vuelve a "IDLE".
3. **Verificar Archivos de Salida**: Una vez que el ciclo termine, puedes conectarte con una tercera terminal (o detener el script con Ctrl+C en la primera) y verificar el resultado:

   - Predicciones NC: `ls -l /app/output_predictions/` (debería haber un nuevo subdirectorio con 5 archivos .nc).
   - Predicciones MDV: `ls -l /app/mdv_predictions/` (debería contener los archivos .mdv renombrados).
   - Entradas Archivadas: `ls -l /app/mdv_archive/` (debería contener tus 12 archivos .mdv originales).
   - Bandeja de Entrada Limpia: `ls -l /app/mdv_inbox/` (debería estar vacía).

### 5. Finalizar la Sesión

- Cuando termines las pruebas, ve al panel de vast.ai y haz clic en "Stop" para detener la instancia y evitar costos innecesarios.