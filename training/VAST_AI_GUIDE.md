# 🚀 Guía de Entrenamiento en vast.ai (H200)

Esta guía detalla el flujo de trabajo completo para entrenar el modelo `ConvLSTM3D_Enhanced` en una instancia de vast.ai.

Existen dos métodos:
1.  **Método Docker (Recomendado):** Usar una imagen pre-construida con todo listo.
2.  **Método Manual:** Instalar todo paso a paso vía SSH.

---

## 🐳 Método 1: Docker (Automatizado)

Este método es más robusto. Creas una "cápsula" con tu código y entorno, y vast.ai la descarga y ejecuta.

### Paso 1: Construir y Subir la Imagen (En tu PC)
Necesitas tener Docker instalado y una cuenta en Docker Hub.

1.  **Login en Docker Hub:**
    ```bash
    docker login
    ```
2.  **Construir la imagen:**
    Desde la carpeta `app_convlstm/training`:
    ```bash
    # Nota: El contexto debe ser un nivel arriba para copiar todo el backend si es necesario
    cd /ruta/a/app_convlstm
    docker build -f training/Dockerfile.training -t tu_usuario/convlstm-training:v1 .
    ```
3.  **Subir la imagen:**
    ```bash
    docker push tu_usuario/convlstm-training:v1
    ```

### Paso 2: Configurar vast.ai
Al alquilar la instancia:

1.  **Image:** Selecciona "Custom Image" y escribe: `tu_usuario/convlstm-training:v1`.
2.  **On-start script:** Copia el contenido del archivo `training/on_start_vast.sh`.
    *   **IMPORTANTE:** Edita el script antes de copiarlo y pon el `DATASET_GDRIVE_ID` real de tu archivo en Drive.
3.  **Disk Space:** Asigna suficiente espacio (ej. 100GB) para que quepa el dataset descomprimido.

### Paso 3: Entrenar
Una vez que la instancia arranque (el botón se ponga azul "Connect"):

1.  Conéctate por SSH.
2.  Verifica que los datos se estén descargando o ya estén listos en `/workspace/data`.
    ```bash
    ls -l /workspace/data
    ```
3.  Configura Rclone para los backups (ver sección Rclone abajo).
4.  Ejecuta el entrenamiento:
    ```bash
    ./run_training.sh 1
    ```

---

## 🛠 Método 2: Manual (SSH)

Si prefieres no usar Docker Hub, usa una imagen base de PyTorch en vast.ai.

1.  **Imagen:** `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel`.
2.  **Subir código:** `scp -P <PORT> -r app_convlstm/ root@<IP>:/workspace/`.
3.  **Instalar:** Ejecuta `./setup_vast.sh`.
4.  **Datos:** Descarga manualmente con `gdown` (ver script `on_start_vast.sh` para referencia).

---

## ☁️ Gestión de Checkpoints (Rclone)

Independientemente del método, usa **Rclone** para guardar tus modelos en Drive.

1.  **Configurar Rclone:**
    ```bash
    rclone config
    # Sigue los pasos para "Google Drive".
    # Al final, usa el comando que te da en tu PC local para autorizar.
    ```

2.  **Subir Checkpoints:**
    ```bash
    # Subir un archivo específico
    rclone copy checkpoints/phase1_best.pth mydrive:Backups_ConvLSTM/

    # Subir toda la carpeta
    rclone copy checkpoints/ mydrive:Backups_ConvLSTM/checkpoints/
    ```

---

## 🔮 Inferencia y Conversión para TITAN

Una vez entrenado el modelo, puedes generar predicciones listas para TITAN directamente en la instancia.

1.  **Ejecutar Inferencia:**
    El script `predict_remote.py` se encarga de:
    *   Leer secuencias de entrada (500x500).
    *   Hacer downsampling a 250x250.
    *   Predecir.
    *   Hacer upsampling a 500x500.
    *   Guardar NetCDF con metadatos correctos.

    ```bash
    python predict_remote.py \
      --sequences_dir /workspace/data \
      --model_path checkpoints/phase3_refinement_best.pth \
      --output_dir /workspace/predictions \
      --input_len 8 \
      --pred_len 7
    ```

2.  **Subir Predicciones a Drive:**
    ```bash
    rclone copy /workspace/predictions mydrive:Predicciones_TITAN/
    ```

---

### Resumen de Comandos

| Acción | Comando |
| :--- | :--- |
| **Construir Docker** | `docker build -f training/Dockerfile.training -t user/img:tag .` |
| **Ver GPU** | `nvidia-smi` |
| **Ver Logs** | `tail -f logs/phaseX.log` |
| **Backup Rápido** | `rclone copy checkpoints/ mydrive:Backups/` |
| **Predecir** | `python predict_remote.py ...` |
