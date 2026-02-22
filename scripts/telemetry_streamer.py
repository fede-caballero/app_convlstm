#!/usr/bin/env python3
"""
TITAN Telemetry Streamer
========================
Run this script on the work PC (where TITAN runs) to stream aircraft
position data in real-time to the VPS backend.

Usage:
    python3 telemetry_streamer.py

Requirements:
    pip install requests

Configuration (Edit the lines below):
"""

import os
import time
import logging
import requests
from datetime import date

# ============================================================
# CONFIGURA ESTOS VALORES ANTES DE EJECUTAR
# ============================================================

# URL de tu VPS (con el túnel de Cloudflare)
VPS_API_URL = "https://vps-api.hail-cast-mendoza.com/api/aircraft/ingest"

# Clave secreta compartida con el servidor (debe coincidir con la del .env del VPS)
INGEST_SECRET_KEY = "t3l3m3try"

# Verificación SSL. Cambiar a False si la red corporativa tiene certificados desactualizados.
# La seguridad está garantizada de todas formas por INGEST_SECRET_KEY.
VERIFY_SSL = False

# Directorio donde TITAN guarda los archivos ascii_ac_posn
# Ej: /home/titan/data/spbd/ascii_ac_posn  o  $DATA_DIR/spbd/ascii_ac_posn
DATA_DIR = os.environ.get("DATA_DIR", "/home/titan5/projDir/data")
ASCII_AC_POSN_DIR = os.path.join(DATA_DIR, "spbd", "ascii_ac_posn")

# ============================================================
# FIN DE CONFIGURACIÓN
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("telemetry_streamer")

# Callsign mapping (TITAN uses "V" prefix, we map to real reg)
CALLSIGN_MAP = {
    "VBCR": "LV-BCR",
    "VBCT": "LV-BCT",
    "VBCU": "LV-BCU",
    "VBCP": "LV-BCP",
    "VBBB": "LV-BBB",
}


def get_today_file():
    """Returns the path to today's telemetry file."""
    today = date.today().strftime("%Y%m%d")
    return os.path.join(ASCII_AC_POSN_DIR, f"{today}.data")


def parse_line(line: str) -> dict | None:
    """
    Parse a telemetry line. Format:
    CALLSIGN,YYYY,MM,DD,HH,MM,SS,LAT,LON,ALT_FT,GS_KT,HEADING_X10,...

    Returns a dict or None if the line is invalid.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split(",")
    if len(parts) < 11:
        return None

    try:
        callsign_raw = parts[0].strip()
        reg = CALLSIGN_MAP.get(callsign_raw, callsign_raw)  # Fallback to raw if unknown

        year, month, day = parts[1], parts[2], parts[3]
        hour, minute, sec = parts[4], parts[5], parts[6]
        timestamp = f"{year}-{month}-{day}T{hour}:{minute}:{sec}Z"

        lat = float(parts[7])
        lon = float(parts[8])
        alt_ft = int(parts[9])
        alt_m = round(alt_ft * 0.3048)
        gs_kt = int(parts[10])
        gs_ms = round(gs_kt * 0.514444, 2)

        heading = round(int(parts[11]) / 10.0) if len(parts) > 11 else 0.0

        return {
            "callsign": callsign_raw,
            "reg": reg,
            "lat": lat,
            "lon": lon,
            "altitude": alt_m,
            "velocity": gs_ms,
            "heading": heading,
            "timestamp": timestamp,
            "source": "titan",
        }
    except (ValueError, IndexError) as e:
        log.warning(f"Error parsing line: '{line}' -> {e}")
        return None


def send_to_vps(aircraft: dict):
    """POST a single aircraft position to the VPS."""
    try:
        response = requests.post(
            VPS_API_URL,
            json=aircraft,
            headers={
                "X-Ingest-Key": INGEST_SECRET_KEY,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; TitanStreamer/1.0)",
            },
            timeout=5,
            verify=VERIFY_SSL,
        )
        if response.status_code == 200:
            log.info(f"✅ Enviado: {aircraft['reg']} @ ({aircraft['lat']:.4f}, {aircraft['lon']:.4f})")
        else:
            log.warning(f"⚠️  VPS respondió {response.status_code}: {response.text[:100]}")
    except requests.exceptions.ConnectionError:
        log.error("❌ No se pudo conectar al VPS. Reintentando en el próximo update...")
    except Exception as e:
        log.error(f"❌ Error al enviar datos: {e}")


def tail_file(filepath: str):
    """Generator that yields new lines appended to a file (like `tail -f`).
    Uses latin-1 encoding since TITAN writes in ISO-8859-1, not UTF-8.
    """
    log.info(f"📡 Monitoreando archivo: {filepath}")
    with open(filepath, "r", encoding="latin-1", errors="replace") as f:
        # Go to the end of the file first (only new data)
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(1)


def main():
    log.info("🛩️  TITAN Telemetry Streamer iniciado.")
    log.info(f"📤 Enviando a: {VPS_API_URL}")

    while True:
        filepath = get_today_file()

        if not os.path.exists(filepath):
            log.warning(f"Archivo de hoy no existe aún: {filepath}. Reintentando en 30s...")
            time.sleep(30)
            continue

        try:
            for line in tail_file(filepath):
                aircraft = parse_line(line)
                if aircraft:
                    send_to_vps(aircraft)
                    
                # Check if the file date has changed (midnight rollover)
                if get_today_file() != filepath:
                    log.info("🌙 Nuevo día detectado, cambiando al archivo de mañana...")
                    break  # Exit inner loop to re-open the new day's file

        except FileNotFoundError:
            log.error(f"Archivo desapareció: {filepath}. Esperando 10s...")
            time.sleep(10)
        except Exception as e:
            log.error(f"Error inesperado: {e}. Reintentando en 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
