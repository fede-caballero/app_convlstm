# 🧠 Estrategia de Fine-Tuning: Secuencias Extendidas (24 y 30 frames)

> **META-PROMPT PARA GEMINI (CUANDO SE IMPORTE ESTE DOCUMENTO):** 
> 
> "Actúa como un AI Engineer experto en arquitectura ConvLSTM3D y transfer learning. Las instrucciones que siguen son el plan técnico definitivo para migrar la arquitectura que entrenaste previamente (de 15 pasos a 24 y luego a 30 pasos). Debes ejecutar las modificaciones asumiendo que **el dataset largo ya está listo y validado**. Tu tarea será modificar `train.py`, `loss.py`, `architecture.py` y generar los nuevos `yaml` de configuración cumpliendo con las especificaciones. No omitas la implementación del script auxiliar para el _surgery_ de los pesos que descarta la última capa convolucional. Lee cada fase con detenimiento."

---

## 🎯 Objetivo General
Empezar a predecir a mayor plazo temporal (hasta $t+15$). Se abandonó el entrenamiento de cero en favor de implementar *Transfer Learning* (Fine-Tuning) sobre el mejor checkpoint de Fase 3. 

El plan asume que el modelo aprendió con éxito las propiedades espaciales (mediante ConvLSTM2DLayer) pero que la capa de mapeo temporal (`output_conv`) está cableada para escupir solo 7 frames y debe reinicializarse. Se aplicará *Curriculum Learning Temporal* subiendo a secuencias de 24 pasos inicialmente y luego de 30, controlando el *Gradient Vanishing* y mitigando el *Blurring* agudo.

---

## 🔧 Componente Clave 1: Reconstrucción de la Arquitectura

### El "Weight Surgery" (Cirugía de Pesos)
Dado que el modelo entrenado tiene una capa final `output_conv` configurada para `out_channels=7`, instanciar un modelo con `pred_steps=12` o `pred_steps=15` generará un crash por *Shape Mismatch* al cargar el `.pth`.

**Requisito de Código:** Al iniciar `train.py` con un flag de `--fine_tune_extend`, se debe saltar la capa `output_conv` al cargar estado.

```python
# Ejemplo de la lógica requerida para la carga de modelo:
# checkpoint = torch.load('checkpoints/phase3_refinement_epoch_100.pth')
# new_state_dict = model.state_dict()
# for name, param in checkpoint['model_state_dict'].items():
#     if "output_conv" not in name:
#         new_state_dict[name] = param
# model.load_state_dict(new_state_dict)
```

---

## 🔧 Componente Clave 2: Reformulación de Hiperparámetros de Pérdida
El error crece exponencialmente a medida que predices pasos más alejados (el difuminado o *Fading Effect*).
La función `CombinedLoss` debe ser más estricta que la Fase 3.

*   `high_penalty_weight`: Subir para forzar que retenga los ecos en los frames finales.
*   `ssim_weight`: Incrementar masivamente si el "blurring" aparece.
*   *(Sugerencia avanzada para Gemini en implementación)*: Considerar un escalado temporal en `loss.py`. Es decir, ponderar la pérdida para que un fallo en $t+1$ cueste 1x, pero un fallo en $t+12$ cueste 2x (forzándolo a enfocarse en los pronósticos lejanos).

---

## 🚀 Plan en 2 Escalones (Fase 4 y Fase 5)

### 📈 Fase 4: Escalón a 24 Frames (12 in / 12 out)
**Objetivo:** Adaptar las celdas de memoria LSTM (i, f, o, g gates) para que retengan memoria un 60% más de tiempo. Es crucial para que los gradientes de BPTT (Backprop Through Time) no exploten.

*   **Punto de Partida:** `checkpoints/phase3_refinement_epoch_100.pth` (Peso de Fase 3)
*   **Archivos a cargar:** (12 in, 12 out) de la muestra pequeña balanceada (~1000 secuencias).
*   **Hardware / VRAM Constraints:** Bajar `batch_size`. Si antes era 16, usar **8**.
*   **Optimizador:** `1e-5` (LR bajo para no destruir la extracción de features base).
*   **Config (phase4_24_steps.yaml):**
    *   `input_steps: 12`, `prediction_steps: 12`
    *   `batch_size: 8`  *// IMPORTANTE: Considerar implementar Gradient Accumulation si batch baja demasiado.*
    *   `epochs: 25`
    *   `loss.high_penalty_weight: 40.0`
    *   `loss.ssim_weight: 40.0`
    *   `training.gradient_clip: 0.1`

---

### 🚀 Fase 5: Refinamiento Final a 30 Frames (15 in / 15 out)
**Objetivo:** Horizonte de predicción máximo (T+15).

*   **Punto de Partida:** El mejor `.pth` resultante de la **Fase 4**.
*   **Config (phase5_30_steps.yaml):**
    *   `input_steps: 15`, `prediction_steps: 15`
    *   `batch_size: 4` (Ojo especial aquí al `LayerNorm` estadístico. Si genera NaNs, Gemini deberá pasarlo a `batch_size: 2` y hacer Micro-Bach/Gradient Acc paso a paso).
    *   `epochs: 20`
    *   `lr: 5e-6`
    *   `loss.high_penalty_weight: 50.0`
    *   `loss.ssim_weight: 50.0`
    *   `training.gradient_clip: 0.05`

---

## 📊 Notas sobre el Nuevo Dataset (Input Data)
A diferencia de la Fase 1-3, este dataset no requiere 2600 muestras. Se conforma con:
*   ~1000 secuencias (para velocidad debido a batch sizes enanos).
*   Mantener balance similar, **pero sobrerepresentando (dando algo más de peso) a Advección, Crecimiento y Decaimiento**. Las secuencias estáticas deben estar minimizadas debido a que no causan el efecto "Blurring" en $t+15$.
*   El tamaño temporal total capturado por carpeta debe permitir extraer 24 o 30 *frames*.
