#!/usr/bin/env python3
"""
Simulador de Telemetría TITAN — Formato Latin-1 (ISO-8859-1)
==============================================================
Genera archivos .data en la misma codificación que usa TITAN real
para que el telemetry_streamer.py los procese exactamente igual
que los datos de vuelo reales.

Uso:
    python3 simulate_telemetry_latin1.py

El streamer debe estar corriendo en paralelo.
"""

import os
import time
import math
from datetime import datetime, timezone, date

# ============================================================
# CONFIGURACIÓN — debe coincidir con telemetry_streamer.py
# ============================================================

DATA_DIR = os.environ.get("DATA_DIR", "/home/titan5/projDir/data")
ASCII_AC_POSN_DIR = os.path.join(DATA_DIR, "spdb", "ac_posn")

# Si querés probar localmente sin path real, descomentá:
# ASCII_AC_POSN_DIR = "/tmp/test_telemetry_latin1"

# Aviones a simular
AIRCRAFT = [
    {
        "callsign": "VBCR",
        "start_lat": -32.89,
        "start_lon": -68.85,
        "radius_deg": 0.10,   # ~11km de radio
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
        "phase_offset": math.pi,
    },
]

INTERVAL_SECONDS = 5

# ============================================================


def get_today_file() -> str:
    today = date.today().strftime("%Y%m%d")
    return os.path.join(ASCII_AC_POSN_DIR, f"{today}.data")


def make_line(callsign: str, lat: float, lon: float,
              alt_ft: int, gs_kt: int, heading: float) -> str:
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

    print("🛩️  Simulador TITAN (Latin-1) iniciado.")
    print(f"📝 Escribiendo en: {filepath}")
    print(f"⚙️  Codificación: latin-1 (ISO-8859-1) — igual que TITAN real")
    print(f"⏱️  Intervalo: {INTERVAL_SECONDS}s")
    print(f"✈️  Aviones: {[ac['callsign'] for ac in AIRCRAFT]}")
    print("─" * 60)

    step = 0
    # Abrimos con encoding='latin-1', igual que escribe TITAN real
    with open(filepath, "a", encoding="latin-1") as f:
        while True:
            for ac in AIRCRAFT:
                angle = (step * INTERVAL_SECONDS / 60.0) * 2 * math.pi / 5 + ac["phase_offset"]
                lat = ac["start_lat"] + ac["radius_deg"] * math.sin(angle)
                lon = ac["start_lon"] + ac["radius_deg"] * math.cos(angle)
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
                f.flush()  # Flush inmediato para que el streamer lo lea al instante
                print(f"  ✅ {line}")

            step += 1
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
