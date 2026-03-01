# Idea para Futuras Implementaciones: Alerta Diaria de Engagement

## Objetivo
Atraer más usuarios a la aplicación y aumentar el engagement enviando una notificación global cuando se detectan tormentas significativas (por ejemplo, mayores a 50 dBZ) en cualquier punto del mapa, incluso si no están cerca de zonas cultivadas o pobladas.

## Flujo de Trabajo Propuesto

1. **Monitoreo de Celdas:**
   Durante el análisis habitual de los archivos del radar (en `pipeline_worker.py`), la función `detect_storm_cells()` identificará los valores máximos de dBZ para cada celda.

2. **Condición de Disparo:**
   Si existe al menos una celda que cumpla con `max_dbz >= 50`, se evalúa enviar una alerta general.

3. **Prevención de Spam (1 vez al día máximo):**
   - El sistema leerá la fecha almacenada en un archivo de caché (ej. `data/last_daily_engagement.txt`).
   - Si la fecha guardada es distinta al día calendario actual (formato YYYYMMDD), significa que hoy todavía no se envió la alerta de engagement.
   - Si la fecha es igual, se ignora el evento (el aviso ya fue enviado más temprano ese mismo día).

4. **Envío de Notificaciones:**
   - Si se supera el control de fecha, el script consultará la tabla `push_subscriptions` y obtendrá todos los usuarios activos.
   - Se emitirá una notificación global, por ejemplo:
     - **Título**: "¡Tormentas detectadas! ⛈️"
     - **Mensaje**: "Hoy hay actividad de tormentas. ¿Ya viste el radar en vivo?"
   - Inmediatamente después del envío, el sistema escribirá el día actual (`YYYYMMDD`) sobreescribiendo `last_daily_engagement.txt`.

## Archivos a Modificar
- **`backend/pipeline_worker.py`**:
  - Crear la función `check_daily_engagement_alerts(storm_cells)`.
  - Instanciar la llamada a esta función dentro de la tubería de análisis principal, cerca donde hoy se ejecutan las Alertas de Proximidad.
