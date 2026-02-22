#!/usr/bin/env python3
"""
TITAN Telemetry Streamer (SPDB Binary Parser)
=============================================
Reads TITAN's binary SPDB ac_posn files directly and streams aircraft
positions to the VPS backend in real-time.

Usage:
    python3 telemetry_streamer.py

Requirements:
    pip install requests

SPDB Binary Format (reverse-engineered from xxd of 20260222.data):
  Each record is 96 bytes, big-endian IEEE 754 floats.
  Offset  0:  fl32  lat        (degrees, MISSING=-9999.0)
  Offset  4:  fl32  lon        (degrees, MISSING=-9999.0)
  Offset  8:  fl32  heading    (degrees true, MISSING=-9999.0)
  Offset 12:  char  callsign[32]  (null-terminated)
  Offset 44:  fl32  alt_ft     (feet, MISSING=-9999.0)
  Offset 48+: other fields (speed, etc.) — mostly MISSING in practice
"""

import os
import struct
import time
import logging
import requests
from datetime import date

# ============================================================
# CONFIGURA ESTOS VALORES ANTES DE EJECUTAR
# ============================================================

VPS_API_URL      = "https://vps-api.hail-cast-mendoza.com/api/aircraft/ingest"
INGEST_SECRET_KEY = "t3l3m3try"
VERIFY_SSL       = False

DATA_DIR          = os.environ.get("DATA_DIR", "/home/titan5/projDir/data")
SPDB_AC_POSN_DIR  = os.path.join(DATA_DIR, "spdb", "ac_posn")

# ============================================================
# FIN DE CONFIGURACIÓN
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("telemetry_streamer")

CALLSIGN_MAP = {
    "VBCR": "LV-BCR",
    "VBCT": "LV-BCT",
    "VBCU": "LV-BCU",
    "VBCP": "LV-BCP",
    "VBBB": "LV-BBB",
}

# TITAN uses -9999.0 as the "no data" sentinel for float fields.
MISSING = -9999.0
MISSING_BYTES = struct.pack(">f", MISSING)   # b'\xc6\x1c<\x00'

# Argentine geographic bounds (sanity check).
LAT_MIN, LAT_MAX = -55.0, -20.0
LON_MIN, LON_MAX =  -75.0, -50.0

# SPDB record layout constants.
RECORD_SIZE      = 96
CALLSIGN_OFFSET  = 12
CALLSIGN_LEN     = 32   # includes null padding


def get_today_file() -> str:
    today = date.today().strftime("%Y%m%d")
    return os.path.join(SPDB_AC_POSN_DIR, f"{today}.data")


def is_valid_coord(val: float, lo: float, hi: float) -> bool:
    return lo <= val <= hi


def parse_record(record: bytes, seen_keys: set) -> dict | None:
    """
    Parse a single 96-byte SPDB ac_posn record.
    Returns a position dict or None if invalid / no new data.
    """
    if len(record) < RECORD_SIZE:
        return None

    # ── unpack the float fields (big-endian) ──────────────────
    lat,     = struct.unpack_from(">f", record,  0)
    lon,     = struct.unpack_from(">f", record,  4)
    heading, = struct.unpack_from(">f", record,  8)
    alt_ft,  = struct.unpack_from(">f", record, 44)
    speed_kt,= struct.unpack_from(">f", record, 48)  # may be MISSING

    # ── callsign ──────────────────────────────────────────────
    raw_cs = record[CALLSIGN_OFFSET: CALLSIGN_OFFSET + CALLSIGN_LEN]
    callsign_raw = raw_cs.split(b"\x00")[0].decode("ascii", errors="replace").strip()
    if not callsign_raw:
        return None

    # ── validate coordinates (skip records with MISSING lat/lon) ─
    valid_lat = is_valid_coord(lat, LAT_MIN, LAT_MAX)
    valid_lon = is_valid_coord(lon, LON_MIN, LON_MAX)
    if not (valid_lat and valid_lon):
        return None

    # ── de-duplicate: skip if lat/lon/callsign haven't changed ──
    dedup_key = (callsign_raw, round(lat, 4), round(lon, 4))
    if dedup_key in seen_keys:
        return None
    seen_keys.add(dedup_key)
    # Keep the set bounded so it doesn't grow unboundedly.
    if len(seen_keys) > 5000:
        seen_keys.clear()

    alt_m   = round(alt_ft * 0.3048) if alt_ft != MISSING else 0
    gs_ms   = round(speed_kt * 0.514444, 2) if speed_kt != MISSING else 0.0
    hdg     = round(heading) if heading != MISSING else 0

    reg = CALLSIGN_MAP.get(callsign_raw, callsign_raw)

    return {
        "callsign":  callsign_raw,
        "reg":       reg,
        "lat":       round(lat, 6),
        "lon":       round(lon, 6),
        "altitude":  alt_m,
        "velocity":  gs_ms,
        "heading":   hdg,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source":    "titan",
    }


def send_to_vps(aircraft: dict) -> None:
    try:
        r = requests.post(
            VPS_API_URL,
            json=aircraft,
            headers={
                "X-Ingest-Key": INGEST_SECRET_KEY,
                "Content-Type": "application/json",
                "User-Agent":   "TitanStreamer/2.0",
            },
            timeout=5,
            verify=VERIFY_SSL,
        )
        if r.status_code == 200:
            log.info(f"✅ {aircraft['reg']} ({aircraft['lat']:.4f}, {aircraft['lon']:.4f})")
        else:
            log.warning(f"⚠️  VPS {r.status_code}: {r.text[:80]}")
    except requests.exceptions.ConnectionError:
        log.error("❌ Sin conexión al VPS.")
    except Exception as e:
        log.error(f"❌ Error HTTP: {e}")


def tail_binary(filepath: str, seen_keys: set):
    """
    Generator that yields parsed aircraft dicts from newly appended
    SPDB records.  Opens in BINARY mode to avoid any encoding issues.
    """
    log.info(f"📡 Monitoreando: {filepath}")
    with open(filepath, "rb") as f:
        f.seek(0, 2)          # seek to end — only watch NEW records
        buf = b""
        while True:
            chunk = f.read(4096)
            if chunk:
                buf += chunk
                # Process all complete 96-byte records in the buffer.
                while len(buf) >= RECORD_SIZE:
                    record = buf[:RECORD_SIZE]
                    buf    = buf[RECORD_SIZE:]
                    result = parse_record(record, seen_keys)
                    if result:
                        yield result
            else:
                time.sleep(1)


def main() -> None:
    log.info("🛩️  TITAN Telemetry Streamer v2 (SPDB binary parser) iniciado.")
    log.info(f"📤 VPS: {VPS_API_URL}")

    seen_keys: set = set()

    while True:
        filepath = get_today_file()

        if not os.path.exists(filepath):
            log.warning(f"Archivo aún no existe: {filepath}. Reintentando en 30s...")
            time.sleep(30)
            continue

        try:
            for aircraft in tail_binary(filepath, seen_keys):
                send_to_vps(aircraft)

                if get_today_file() != filepath:
                    log.info("🌙 Cambio de día, reabriendo archivo...")
                    break

        except FileNotFoundError:
            log.error(f"Archivo desapareció: {filepath}. Esperando 10s...")
            time.sleep(10)
        except Exception as e:
            log.error(f"Error inesperado: {e}. Reintentando en 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
