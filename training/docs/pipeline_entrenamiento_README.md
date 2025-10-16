
# Contexto y Plan del Pipeline de Entrenamiento del Modelo ConvLSTM

## 1. Objetivo General

El objetivo principal es migrar de un proceso de entrenamiento manual y experimental basado en Jupyter Notebooks a un **pipeline de entrenamiento robusto, reproducible y automatizado** utilizando Docker.

Esto nos permitirá iterar en la mejora del modelo de forma sistemática, gestionar el entorno de forma consistente y facilitar la ejecución de entrenamientos en diferentes máquinas (locales o remotas como Vast.ai).

## 2. Estrategia de Entrenamiento Acordada

- **Modelo Base**: Continuar usando la arquitectura **ConvLSTM** actual para establecer una línea base sólida. Mejoras futuras (como mecanismos de atención o arquitecturas como TrajGRU) se explorarán DESPUÉS de tener un baseline funcional.
- **Datos de Entrada**: El pipeline espera archivos NetCDF (.nc) con una resolución de 500x500x18.
- **Pre-procesamiento (Downsampling)**: El script de entrenamiento realiza un **downsampling al vuelo a 250x250** usando `xarray`. Esto se hace para reducir el consumo de VRAM y permitir un modelo más profundo o un batch size más grande.
- **Tamaño de Secuencia**: Se ha aumentado la complejidad temporal para capturar mejor la dinámica. La configuración actual es de **18 frames de entrada para predecir 7 frames de salida** (secuencia total de 25).
- **Data Augmentation**: Se utilizan **ventanas deslizantes (sliding windows)** sobre los datos para multiplicar la cantidad de muestras de entrenamiento a partir de los mismos eventos, permitiendo que el modelo aprenda de diferentes etapas de las tormentas.

## 3. Estado Actual y Componentes Creados

Se ha creado una nueva carpeta `training/` en la raíz del proyecto que contiene todos los componentes del nuevo pipeline:

- **`training/requirements.train.txt`**:
  - **Propósito**: Archivo de texto que lista todas las dependencias de Python necesarias para el entrenamiento (`torch`, `xarray`, `torchmetrics`, `gdown`, etc.).
  - **Uso**: Se utiliza en el Dockerfile para instalar un entorno consistente.

- **`training/Dockerfile.train`**:
  - **Propósito**: Define la imagen de Docker para el entrenamiento.
  - **Detalles**:
    - Usa una imagen base oficial de **PyTorch con soporte para CUDA 12.1**.
    - Instala dependencias del sistema como `pigz` (para descompresión paralela más rápida).
    - Copia el código fuente (`backend/` y `training/`) a la imagen.
    - Instala las librerías de Python usando el archivo `requirements.train.txt`.
    - El comando por defecto es ejecutar el script `train_worker.py`.

- **`training/train_worker.py`**:
  - **Propósito**: Es el script principal que orquesta todo el pipeline de entrenamiento de forma automatizada.
  - **Funcionalidades**:
    1.  **Configuración Centralizada**: Todos los parámetros (rutas, tamaño de secuencia, learning rate, etc.) están en un diccionario `CONFIG` al inicio del archivo.
    2.  **Preparación del Dataset**: Una función `setup_dataset` se encarga de descargar el dataset desde Google Drive con `gdown` y descomprimirlo si no se encuentra localmente.
    3.  **Carga de Datos**: La clase `RadarDataset` carga los archivos `.nc`, aplica el **downsampling a 250x250** y prepara los tensores para el modelo.
    4.  **División de Datos**: La función `prepare_and_split_data` organiza los eventos cronológicamente, los divide en conjuntos de entrenamiento/validación y genera las secuencias usando ventanas deslizantes.
    5.  **Entrenamiento**: La función `train_model` contiene el bucle de entrenamiento y validación, implementando lógicas avanzadas como:
        - Mixed Precision (`torch.amp`) para acelerar el entrenamiento.
        - Acumulación de gradientes para simular un `batch_size` mayor.
        - Una función de pérdida combinada (Huber + SSIM).
    6.  **Checkpointing**: Guarda el mejor modelo basado en la pérdida de validación y checkpoints periódicos de cada época.

## 4. Flujo de Trabajo y Comandos

Todo se ejecuta desde la terminal en la máquina host (ej. la instancia de Vast.ai).

### Paso 1: Construir la Imagen de Docker
*Este comando solo se necesita ejecutar una vez, o si se modifica el Dockerfile o los requirements.*

```bash
docker build -t convlstm-training -f training/Dockerfile.train .
```

### Paso 2: Ejecutar el Entrenamiento (Modo Producción)
*Este comando inicia el pipeline. Los datos y modelos generados se guardarán en tu máquina host.*

```bash
docker run --gpus all -it --rm \
  -v $(pwd)/model_output:/app/model_output \
  -v $(pwd)/datasets:/app/datasets \
  convlstm-training
```
- `--gpus all`: Da acceso a la GPU.
- `-v $(pwd)/model_output:/app/model_output`: Sincroniza la carpeta local `model_output` con la de salida del contenedor. **Aquí aparecerán tus modelos entrenados**.
- `-v $(pwd)/datasets:/app/datasets`: Sincroniza la carpeta local `datasets`. **Aquí se descargará y vivirá tu dataset**.

### Paso 3: Ejecutar para Desarrollo (Modo Interactivo)
*Usa este comando si quieres editar el código Python y que los cambios se apliquen sin tener que reconstruir la imagen de Docker.*

```bash
docker run --gpus all -it --rm \
  -v $(pwd)/backend:/app/backend \
  -v $(pwd)/training:/app/training \
  -v $(pwd)/model_output:/app/model_output \
  -v $(pwd)/datasets:/app/datasets \
  convlstm-training
```
- Se añaden `-v` para las carpetas `backend` y `training`, reflejando cualquier cambio en el código al instante dentro del contenedor.

## 5. Próximos Pasos

1.  **Construir la imagen Docker** usando el comando del "Paso 1".
2.  **Ejecutar el entrenamiento** usando el comando del "Paso 2".
3.  **Monitorear la salida** en la terminal para ver los logs de pérdida y el progreso.
4.  **Verificar los resultados**: Una vez finalizado, la carpeta `model_output` en tu máquina contendrá los archivos `.pth` del modelo y los checkpoints.
