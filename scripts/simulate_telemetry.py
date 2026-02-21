#!/usr/bin/env python3
"""
Simulador de Telemetría TITAN
==============================
Genera líneas de telemetría falsas en el formato ascii_ac_posn de TITAN
y las escribe al archivo del día para que telemetry_streamer.py las envíe al VPS.

Uso:
    python3 simulate_telemetry.py

El streamer debe estar corriendo en paralelo para que envíe los datos al VPS.
"""

import os
import time
import math
from datetime import datetime, timezone, date

# ============================================================
# CONFIGURACIÓN DEL SIMULADOR
# ============================================================

# Directorio donde TITAN guarda los archivos ascii_ac_posn
# Debe ser la misma que la configurada en telemetry_streamer.py
DATA_DIR = os.environ.get("DATA_DIR", "/home/titan5/projDir/data")
ASCII_AC_POSN_DIR = os.path.join(DATA_DIR, "spbd", "ascii_ac_posn")

# Si querés probar localmente sin configurar rutas, usa una carpeta temporal:
# ASCII_AC_POSN_DIR = "/tmp/test_telemetry"

# Aviones a simular
AIRCRAFT = [
    {
        "callsign": "VBCR",
        # Ruta circular sobre Mendoza (centro: -32.89, -68.85)
        "start_lat": -32.89,
        "start_lon": -68.85,
        "radius_deg": 0.10,  # ~11km de radio
        "alt_ft": 10000,
        "gs_kt": 120,
        "phase_offset": 0,
    },
    {
        "callsign": "VBCT",
        "start_lat": -32.89,
        "start_lon": -68.85,
        "radius_deg": 0.07,
        "alt_ft": 8000,
        "gs_kt": 100,
        "phase_offset": math.pi,  # Empezar en el lado opuesto del círculo
    },
]

INTERVAL_SECONDS = 5  # Cada cuántos segundos se escribe una nueva posición

# ============================================================


def get_today_file() -> str:
    today = date.today().strftime("%Y%m%d")
    return os.path.join(ASCII_AC_POSN_DIR, f"{today}.data")


def make_line(callsign: str, lat: float, lon: float, alt_ft: int, gs_kt: int, heading: float) -> str:
    """Genera una línea en el formato TITAN ascii_ac_posn."""
    now = datetime.now(timezone.utc)
    heading_x10 = int(heading * 10)
    return (
        f"{callsign},"
        f"{now.year},{now.month:02d},{now.day:02d},"
        f"{now.hour:02d},{now.minute:02d},{now.second:02d},"
        f"{lat:.4f},{lon:+010.4f},"
        f"{alt_ft:05d},{gs_kt:03d},{heading_x10:04d},"
        f"0,0,0,0,000,000,000"
    )


def main():
    os.makedirs(ASCII_AC_POSN_DIR, exist_ok=True)
    filepath = get_today_file()

    print(f"🛩️  Simulador TITAN iniciado.")
    print(f"📝 Escribiendo en: {filepath}")
    print(f"⏱️  Intervalo: {INTERVAL_SECONDS}s")
    print(f"✈️  Aviones: {[ac['callsign'] for ac in AIRCRAFT]}")
    print("─" * 50)

    step = 0
    with open(filepath, "a") as f:
        while True:
            for ac in AIRCRAFT:
                # Calcular posición en la ruta circular
                angle = (step * INTERVAL_SECONDS / 60.0) * 2 * math.pi / 5 + ac["phase_offset"]
                lat = ac["start_lat"] + ac["radius_deg"] * math.sin(angle)
                lon = ac["start_lon"] + ac["radius_deg"] * math.cos(angle)

                # Heading es la tangente al círculo (perpendicular al radio)
                heading = (math.degrees(angle) + 90) % 360

                line = make_line(
                    callsign=ac["callsign"],
                    lat=lat,
                    lon=lon,
                    alt_ft=ac["alt_ft"],
                    gs_kt=ac["gs_kt"],
                    heading=heading,
                )
                f.write(line + "\n")
                f.flush()  # Importante: flush para que el streamer lo lea al instante
                print(f"  ✅ {line}")

            step += 1
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
