# Análisis de Pipeline Dual Secuencial (San Rafael y San Martín)

Actualmente, el sistema está diseñado alrededor de un ciclo infinito en `pipeline_worker.py` que lee archivos `.mdv` de un único directorio de entrada (`MDV_INBOX_DIR`), los convierte, y ejecuta la inferencia. 

Para procesar imágenes de dos radares (San Rafael y San Martín) **de manera secuencial** y priorizando San Rafael sin problemas de condiciones de carrera (race conditions) ni saturación de RAM/VRAM, se propone la siguiente arquitectura:

## 1. Separación de Directorios de Entrada

El primer problema de usar un mismo directorio es que las secuencias de 4 imágenes necesarias para la inferencia se mezclarían (ej. 3 de San Rafael y 1 de San Martín), rompiendo la lógica espacial del modelo. 

Se deben separar las carpetas base:
- `data/san_rafael/inbox` -> `data/san_rafael/inputs` -> `data/san_rafael/outputs`
- `data/san_martin/inbox` -> `data/san_martin/inputs` -> `data/san_martin/outputs`

## 2. Lógica de "Master Worker" Secuencial

En lugar de tener dos procesos de Docker/Python corriendo en paralelo (lo cual consumiría el doble de RAM al cargar dos instancias del modelo LSTM), se debe modificar el `pipeline_worker.py` actual para que actúe como un arbitro secuencial.

El worker tendrá **una única instancia** del modelo cargada en memoria (`ModelPredictor(MODEL_PATH)`).

En cada ciclo (`while True:`), el worker hará lo siguiente:

1. **Revisar San Rafael (Prioridad Alta):**
   - Leer cuántos `.mdv` hay en `san_rafael/inbox`.
   - Si hay nuevos, convertirlos a NetCDF.
   - Si la secuencia de NetCDF de San Rafael alcanza la longitud requerida (4), **ejecutar la inferencia de San Rafael** y guardar resultados.
   - *Si se ejecutó inferencia de San Rafael, reiniciar el ciclo `continue` (así siempre vuelve a revisar San Rafael primero).*

2. **Revisar San Martín (Prioridad Baja):**
   - Si no hubo nada suficiente para procesar en San Rafael, revisar `san_martin/inbox`.
   - Si hay nuevos `.mdv`, convertirlos a NetCDF.
   - Si la secuencia de NetCDF de San Martín alcanza la longitud requerida (4), **ejecutar la inferencia de San Martín** y guardar resultados.

## 3. Impacto en el Frontend y Base de Datos

- **Visor Dual:** El frontend actualmente lee de una carpeta de imágenes estática (`static/images/inputs` y `static/images/predictions`). Esto tendría que cambiar para soportar dos mapas o un selector ("Ver San Rafael" / "Ver San Martín").
- **Endpoints de la API:** Modificar `api.py` para que los endpoints reciban un parámetro de radar (ej. `/api/images?radar=san_rafael`).
- **Estados:** El archivo de `status.json` debe reflejar el estado de ambos pipelines por separado para que la barra de administrador funcione bien.

## Conclusión sobre Complejidad

**¿Es muy complejo de sincronizar?** 
No es complejo a nivel de la máquina o el modelo, ya que un único ciclo secuencial (Single-Thread) elimina por definición cualquier riesgo de ejecución simultánea. El modelo en RAM se reutiliza para ambos.

**El verdadero desafío es el refactorizado:** Para que esto funcione, hay que actualizar bastantes rutas estáticas de carpetas (cambiar variables globales por argumentos de funciones) tanto en el backend (`pipeline_worker.py`, `api.py`) como introducir la capacidad de elegir el radar en el estado global del frontend (React).
