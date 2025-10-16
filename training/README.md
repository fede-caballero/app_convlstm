# Estrategia de Entrenamiento del Modelo ConvLSTM

Este documento detalla una estrategia de entrenamiento en dos fases para el modelo ConvLSTM, diseñada para optimizar el aprendizaje y la calidad de las predicciones.

## Resumen de la Estrategia

El entrenamiento se divide en dos fases principales:

1.  **Fase 1: Estabilización Inicial.** El objetivo es que el modelo aprenda a generar predicciones con celdas de alta reflectividad, superando el problema inicial de producir solo valores bajos.
2.  **Fase 2: Refinamiento y Generalización.** Una vez que el modelo es capaz de predecir tormentas intensas, se ajustan los hiperparámetros para mejorar la precisión estructural (SSIM) y la calidad general de la predicción en todo el rango de reflectividades.

---

## Fase 1: Estabilización Inicial

**Objetivo:** Forzar al modelo a predecir valores de alta reflectividad (tormentas) y establecer una base de aprendizaje estable.

**Duración Sugerida:** 15-25 épocas.

### Hiperparámetros Recomendados:

*   **`EPOCHS`**: `25`
*   **`BATCH_SIZE`**: `4` (o el máximo que permita tu VRAM, como `8` o `12` en la H200). Un batch size mayor puede acelerar el entrenamiento y estabilizar el gradiente.
*   **`LEARNING_RATE`**: `1e-4` (un valor estándar para empezar con Adam).
*   **`SSIM_LOSS_WEIGHT`**: `0.1` (inicialmente bajo para no penalizar demasiado la estructura y centrarnos en el error de píxel).
*   **`HIGH_DBZ_THRESHOLD_NORM`**: `0.75` (umbral alto para definir qué es "alta reflectividad").
*   **`HIGH_PENALTY_WEIGHT`**: `100` (penalización muy alta para los errores en píxeles de alta reflectividad, forzando al modelo a aprenderlos).

---

## Fase 2: Refinamiento y Generalización

**Objetivo:** Mejorar la calidad estructural de las predicciones (SSIM) y el rendimiento general del modelo, una vez que ya no ignora las altas reflectividades.

**Requisito:** Haber completado la Fase 1 o tener un modelo que ya predice altas reflectividades. Se debe cargar el `best_convLSTM_model.pth` de la fase anterior.

**Duración Sugerida:** 25+ épocas.

### Hiperparámetros Recomendados:

*   **`EPOCHS`**: `50` (o más, hasta que la pérdida de validación se estanque).
*   **`BATCH_SIZE`**: Mantener el valor de la Fase 1.
*   **`LEARNING_RATE`**: `5e-5` (reducir el learning rate para un ajuste fino).
*   **`SSIM_LOSS_WEIGHT`**: `0.4` (aumentar el peso de SSIM para dar más importancia a la similitud estructural).
*   **`HIGH_DBZ_THRESHOLD_NORM`**: `0.5` (reducir el umbral para considerar un rango más amplio de reflectividades como importante).
*   **`HIGH_PENALTY_WEIGHT`**: `40` (reducir la penalización, ya que el modelo ya debería estar prestando atención a las altas reflectividades).

---

## Generación de Predicciones Post-Entrenamiento

Una vez finalizado el ciclo de entrenamiento, se cargará el mejor modelo guardado (`best_convLSTM_model.pth`) y se generarán predicciones sobre el conjunto de validación. Estas predicciones se guardarán en la carpeta `predictions_output` en formato NetCDF (`.nc`), permitiendo su descarga y análisis local.
