# 🧠 Estrategia de Entrenamiento del Modelo PredRNN++ para Predicción de Radar

Este documento describe una **estrategia de entrenamiento optimizada en múltiples fases** para el modelo **PredRNN++**, adaptada al caso de predicción de tormentas severas con reflectividades radar (DBZ) en formato NetCDF.

El enfoque está diseñado para:
- Capturar la **advección real** de celdas convectivas (evitando que el modelo “engorde” los ecos).
- Mejorar la **coherencia estructural y temporal** de las predicciones.
- Controlar los costos de GPU en la H200.
- Mantener compatibilidad total con los archivos **NetCDF** originales (preservando metadatos para reconversión posterior).

---

## 📦 Configuración de Entradas y Salidas

- **Entrada:** 10 imágenes (frames) consecutivas cada 3–4 minutos.
- **Salida:** 5 imágenes futuras (horizonte de 15–20 minutos).
- **Formato:** NetCDF (`DBZ(time, z, y, x)`).
- **Normalización:**  
  ```python
  dbz = np.clip(dbz, -29, 65)
  dbz_norm = (dbz + 29) / (65 + 29)
  ```
- **Downsampling inteligente:**  
  En lugar de un `resize` estándar, se recomienda un **average pooling 2D**:
  ```python
  import torch.nn.functional as F
  x_down = F.avg_pool2d(x, kernel_size=2)  # 500x500 → 250x250
  ```
  ✅ Preserva las estructuras convectivas  
  ✅ Reduce la VRAM hasta 75%  
  ✅ Mantiene la compatibilidad de metadatos (solo requiere registrar el nuevo tamaño en el NetCDF final)

---

## ⚙️ Arquitectura del Modelo

### 🔹 Modelo: PredRNN++
El modelo usa **memorias espaciotemporales acopladas (C, M)** que mejoran la representación de desplazamientos y deformaciones de celdas convectivas.

Ventajas:
- Representa la **advección natural** sin “hinchar” las celdas.
- Preserva **estructuras intensas (>35 dBZ)**.
- Escalable con el tamaño de batch.

---

## 🧩 Estrategia Multietapa de Entrenamiento

El entrenamiento se divide en **tres fases**.  
Cada fase tiene un objetivo distinto en el proceso de aprendizaje.

---

### 🥇 Fase 1 — Estabilización Inicial
**Objetivo:** que el modelo empiece a reproducir tormentas intensas y evite outputs uniformes o con baja reflectividad.

**Duración sugerida:** 20–25 épocas.

| Parámetro | Valor | Justificación |
|------------|--------|---------------|
| `EPOCHS` | 25 | suficiente para estabilizar salida |
| `BATCH_SIZE` | 8–12 (según VRAM) | mejora la estabilidad de gradiente |
| `LEARNING_RATE` | 1e-4 | base estable para Adam |
| `SSIM_LOSS_WEIGHT` | 0.1 | prioriza error por píxel |
| `HIGH_DBZ_THRESHOLD_NORM` | 0.75 | destaca ecos fuertes |
| `HIGH_PENALTY_WEIGHT` | 100 | fuerza el aprendizaje de tormentas |
| `OPTIMIZER` | Adam (β1=0.9, β2=0.999) | estándar robusto |

💡 **Consejo:**  
Aplicar *gradient clipping* (`torch.nn.utils.clip_grad_norm_`) para evitar explosión de gradientes en las primeras épocas.

---

### 🥈 Fase 2 — Refinamiento Estructural
**Objetivo:** mejorar la coherencia estructural y la similitud espacial (SSIM), sin perder intensidad.

**Duración sugerida:** 40–60 épocas.

| Parámetro | Valor | Justificación |
|------------|--------|---------------|
| `EPOCHS` | 50 | permite consolidar la memoria espaciotemporal |
| `LEARNING_RATE` | 5e-5 | ajuste fino |
| `SSIM_LOSS_WEIGHT` | 0.4 | mayor énfasis en estructura |
| `HIGH_DBZ_THRESHOLD_NORM` | 0.5 | cubre más rango de reflectividades |
| `HIGH_PENALTY_WEIGHT` | 40 | reduce penalización para balancear |
| `SCHEDULER` | CosineAnnealingLR o ReduceLROnPlateau | mejora la convergencia final |

📈 En esta fase, el modelo debe ser capaz de seguir **trayectorias de celdas individuales** y **preservar divisiones y fusiones**.

---

### 🥉 Fase 3 — Estabilización Avanzada (Fine-Tuning Global)
**Objetivo:** ajustar detalles finos y eliminar fluctuaciones o “alucinaciones” locales.

**Duración sugerida:** 20–30 épocas.

| Parámetro | Valor | Justificación |
|------------|--------|---------------|
| `EPOCHS` | 30 | fine-tuning final |
| `LEARNING_RATE` | 1e-5 | ultra fino |
| `SSIM_LOSS_WEIGHT` | 0.6 | maximiza la coherencia estructural |
| `HIGH_PENALTY_WEIGHT` | 20 | penalización suave |
| `REGULARIZACIÓN` | Dropout 0.1 o Weight Decay 1e-5 | evita sobreajuste |

🎯 En esta etapa se puede aplicar *early stopping* basado en **SSIM promedio** o **MSE de alta reflectividad**.

---

## 🧮 Métricas de Evaluación

Se recomienda monitorear:

| Métrica | Descripción |
|----------|--------------|
| **MSE / RMSE** | Error general de reflectividad. |
| **SSIM** | Coherencia estructural espacial. |
| **CSI (>35 dBZ)** | Tasa de acierto de tormentas intensas. |
| **Bias (>35 dBZ)** | Sobre o subestimación de eventos fuertes. |
| **FAR (False Alarm Rate)** | Control de alucinaciones. |

💡 Ponderar más los píxeles >35 dBZ en todas las métricas.

---

## 💾 Guardado de Modelos y Predicciones

- Guardar el mejor modelo con:
  ```python
  if val_loss < best_loss:
      torch.save(model.state_dict(), "best_predrnn_model.pth")
  ```

- Generar predicciones post-entrenamiento y exportarlas a NetCDF:
  ```python
  import xarray as xr

  pred_nc = xr.Dataset(
      {"DBZ_pred": (("time", "z", "y", "x"), pred_array)},
      coords={"time": time_coords, "z": z_levels, "y": y_coords, "x": x_coords},
      attrs=metadata_original
  )
  pred_nc.to_netcdf("predictions_output/pred_case.nc")
  ```

✅ Esto asegura compatibilidad total con tus herramientas de análisis actuales (TITAN, Py-ART, etc.).

---

## 📊 Consejos finales para la H200

- VRAM disponible (80 GB) → aprovechar con `batch_size=12–16` y `mixed_precision` (`torch.cuda.amp`).
- Downsampling 2× mantiene coherencia espacial sin perder metadatos.
- PredRNN++ con 10→5 secuencias es el **equilibrio óptimo** entre precisión, costo y estabilidad.
- No es necesario más de 3 capas ocultas (`hidden_dims=[64,64,64]`).

---

## 🧩 Resumen Global

| Fase | Épocas | LR | Batch | SSIM W | HighPenalty | Objetivo |
|------|---------|----|--------|---------|--------------|-----------|
| 1 | 25 | 1e-4 | 8–12 | 0.1 | 100 | Aprendizaje de ecos fuertes |
| 2 | 50 | 5e-5 | 8–12 | 0.4 | 40 | Coherencia estructural |
| 3 | 30 | 1e-5 | 8–12 | 0.6 | 20 | Refinamiento global |

Total recomendado: **~100–110 épocas**  
→ Con early stopping, se logra un modelo muy sólido y físicamente coherente.

---

## 🚀 Resultado Esperado

- Advección realista y desplazamientos suaves de celdas.
- Preservación de reflectividades >35 dBZ sin inflado.
- Reducción de falsos positivos (“alucinaciones”).
- Predicciones físicamente coherentes hasta 20 minutos adelante.

---

## 🧩 Futuras Mejoras Opcionales

- Añadir un **bloque de atención temporal** (Temporal Self-Attention) en la salida del encoder.
- Combinar PredRNN++ con **PhydNet-style regularization** (basado en ecuaciones de advección-difusión).
- Incluir una cuarta **fase de reentrenamiento corto** con datos balanceados en intensidad para corregir sesgos.

---

✍️ **Autor:** Federico Caballero  
📚 **Proyecto de Tesis:** Predicción de tormentas severas mediante redes espaciotemporales (PredRNN++)  
🧩 **Framework:** PyTorch  
💾 **Entrenamiento en GPU:** NVIDIA H200