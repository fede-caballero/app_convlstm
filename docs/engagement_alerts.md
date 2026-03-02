# Idea para Futuras Implementaciones: Alerta Diaria de Engagement

## Objetivo
Atraer más usuarios a la aplicación y aumentar el engagement enviando una notificación global cuando se detectan tormentas significativas en el oasis cultivado, minimizando los falsos positivos (ecos fijos de cerros/cordillera o glitches al encender el radar).

## Reglas de Disparo y Prevención de Falsos Positivos

1. **Intensidad y Ubicación:**
   - Solo se tomarán en cuenta celdas que cumplan con la condición: `max_dbz >= 55`.
   - Se debe calcular la distancia desde la celda hasta el centroide del área cultivada (ej. Radar San Martín o Centro de Mendoza). Solo son válidas si la distancia es `< 70 km`. Esto filtra los ecos fijos de las montañas al sur y al oeste.

2. **Ventana Horaria:**
   - Las notificaciones solo pueden dispararse si la hora local de Mendoza (UTC-3) está entre las **10:00 y las 23:00**. 

3. **Confirmación de 30 minutos (Protección del Radar):**
   - Cuando se detecta una celda válida por primera vez, el sistema **no** envía la alerta inmediatamente. Se registra este momento como un estado "Pendiente".
   - El sistema debe esperar 30 minutos. Si el radar sigue encendido transcurrido este plazo (es decir, siguen ingresando imágenes) y continúan habiendo celdas válidas que cumplan las condiciones, recién ahí se envía el Push.
   - Si el radar se apaga antes de los 30 min (no llegan nuevas imágenes), o desaparecen las celdas, la alerta "Pendiente" se aborta, previniendo spam.

4. **Prevención de Spam (1 vez al día máximo):**
   - El sistema leerá la fecha almacenada en `data/last_daily_engagement.txt`.
   - Si ya se envió un aviso exitoso en el día calendario actual (`YYYYMMDD` en hora local), se desactiva por el resto del día.

## Flujo de Trabajo a Programar
- **`backend/pipeline_worker.py`**:
  - Crear la función `check_daily_engagement_alerts(storm_cells)`.
  - Usar un archivo JSON temporal (o variable global en el hilo) `data/pending_engagement.json` para guardar:
    - `first_detection_time`: Timestamp de la primera celda válida detectada hoy.
  - El evaluador:
    - ¿Están dadas las condiciones de DBZ y Distancia?
    - ¿La hora actual está entre las 10:00 y las 23:00?
    - ¿Se superó el cooldown de 30 minutos desde `first_detection_time`?
    - Si todo es SÍ -> **Enviar Push Global**, registrar en `last_daily_engagement.txt` y borrar `pending_engagement.json`.
