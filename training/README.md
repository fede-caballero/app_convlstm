# 🧠 Estrategia de Entrenamiento: ConvLSTM3D (Enhanced)

Este documento detalla la estrategia de entrenamiento multietapa diseñada para el modelo **ConvLSTM3D_Enhanced**.

El objetivo principal es superar las limitaciones arquitectónicas de las redes recurrentes convolucionales (tendencia al "difuminado" o *blurriness*) y forzar el aprendizaje de vectores de advección (movimiento) reales, aprovechando la infraestructura de cómputo de alto rendimiento.

---

## ⚙️ Configuración del Entorno y Datos

Para maximizar la estabilidad de los gradientes y la capacidad de generalización, se ha redefinido la configuración base del experimento:

| Componente | Configuración | Justificación |
| :--- | :--- | :--- |
| **Dataset** | **2000 Secuencias** | Dataset masivo balanceado (Advección, Multicelda, Supercelda) para reducir la varianza. |
| **Ratio I/O** | **8 Entrada / 7 Salida** | Relación ~1:1. Provee suficiente contexto histórico (24-32 min) para inferir aceleración. |
| **Resolución** | **250 x 250 x 18** | **Downsampling 2x**. Reduce el consumo de VRAM x4, permitiendo *Batch Sizes* grandes. |
| **Batch Size** | **16 – 32** | Crítico para que `GroupNorm` estabilice los gradientes y evite mínimos locales. |
| **Hardware** | **NVIDIA H200 (141GB)** | Permite alojar el grafo computacional 5D con lotes grandes. |

---

## 📉 Pipeline de Pre-procesamiento y Post-procesamiento

La estrategia se basa en la **optimización dimensional**: entrenar rápido en resolución media y visualizar en alta resolución.

1.  **Ingesta:** NetCDF Original (500x500) $\to$ `AveragePooling2D` $\to$ Tensor (250x250).
2.  **Entrenamiento:** El modelo aprende sobre la grilla de 250px (suficiente para capturar la macro-física de la tormenta).
3.  **Inferencia:** Predicción (250x250) $\to$ `Bicubic Upsampling` $\to$ NetCDF (500x500) $\to$ **TITAN**.

---

## 🚀 Plan de Entrenamiento en 3 Fases

El entrenamiento no es monolítico. Se utiliza **Curriculum Learning** para guiar al modelo desde la detección de intensidad hasta el refinamiento morfológico.

### 🥇 Fase 1: "Burn-in" Físico (Intensidad y Ubicación)
**Objetivo:** Forzar al modelo a predecir núcleos convectivos fuertes en la ubicación correcta, ignorando por ahora la forma exacta.

* **Duración:** 0 $\to$ 25 Épocas (o hasta estabilizar `Val Loss`).
* **Optimizador:** AdamW (`lr=1e-3` con Warmup).

| Hiperparámetro | Valor | Razón Técnica |
| :--- | :---: | :--- |
| `HIGH_PENALTY_WEIGHT` | **100** | Penalización masiva. Obliga a la red a "activarse" ante ecos >40 dBZ. |
| `SSIM_WEIGHT` | **0.1** | Despreciable. Evita que el modelo colapse intentando perfeccionar bordes prematuramente. |
| `LOSS_FUNCTION` | Huber + Weighted | Prioridad a minimizar el error numérico bruto. |

---

### 🥈 Fase 2: Corrección de Advección (El "Anti-Engorde")
**Objetivo Crítico:** Transformar la "mancha que crece" en una "celda que se desplaza". Aquí atacamos el problema del difuminado.

* **Duración:** 26 $\to$ 75 Épocas.
* **Optimizador:** `lr=1e-4` (Scheduler: `ReduceLROnPlateau`, paciencia=4).

| Hiperparámetro | Valor | Razón Técnica |
| :--- | :---: | :--- |
| `HIGH_PENALTY_WEIGHT` | **50** | Se reduce la presión sobre el valor del píxel individual. |
| `SSIM_WEIGHT` | **20** | **Aumento agresivo (x200).** El SSIM penaliza severamente las manchas borrosas. |
| **Efecto Esperado** | Agudeza | Una celda nítida en movimiento tiene mejor *Loss* que una mancha estática. |

> 💡 **Nota:** En esta fase es donde el modelo "aprende a mover" la tormenta. Si el modelo sigue "engordando" las celdas, incrementar `SSIM_WEIGHT` a 30.

---

### 🥉 Fase 3: Refinamiento "High-Frequency"
**Objetivo:** Limpiar artefactos de fondo (ruido en capas bajas) y recuperar picos extremos de granizo.

* **Duración:** 76 $\to$ 100+ Épocas.
* **Optimizador:** `lr=1e-5` (Scheduler: `CosineAnnealing` para convergencia suave).

| Hiperparámetro | Valor | Razón Técnica |
| :--- | :---: | :--- |
| `HIGH_PENALTY_WEIGHT` | **25** | Balance final. |
| `SSIM_WEIGHT` | **30** | Prioridad máxima a la estructura y textura de la tormenta. |
| `GRADIENT_CLIP` | **0.1** | *Clipping* agresivo para evitar saltos bruscos que dañen los pesos finos. |

---

## 📊 Métricas de Éxito (KPIs)

El éxito del entrenamiento no se mide solo por la *Loss* global. Monitorear:

1.  **CSI (Critical Success Index) @ 35 dBZ:** Debe superar el 0.4 para ser operativo.
2.  **Visualización Cualitativa:**
    * ¿La celda se desplaza o se estira?
    * ¿Se conservan los núcleos rojos (>50 dBZ) en $t+15$?
3.  **Comparativa vs. TITAN:** La predicción debe mostrar deformación no lineal, superando la extrapolación de elipsoides rígidos.

---

## 🛠 Comandos de Ejecución

```bash
# Fase 1
python train.py --config configs/phase1_burnin.yaml --batch_size 32

# Fase 2 (Cargando pesos de Fase 1)
python train.py --config configs/phase2_advection.yaml --resume_from checkpoints/phase1_best.pth

# Inferencia y Conversión para TITAN
python predict_pipeline.py --model_path checkpoints/phase3_best.pth --upsample True