#!/usr/bin/env python3
"""
TITAN Telemetry Streamer v3 — SpdbQuery-based
==============================================
Uses the LROSE `SpdbQuery` tool to read aircraft positions directly from
the SPDB database (spdb/ac_posn), avoiding all binary parsing issues.

Usage:
    python3 telemetry_streamer.py

Requirements:
    pip install requests
    SpdbQuery must be in PATH or LROSE_BIN must be set.

Configuration (edit below):
"""

import os
import re
import time
import logging
import subprocess
import requests

# ============================================================
# CONFIGURA ESTOS VALORES ANTES DE EJECUTAR
# ============================================================

VPS_API_URL       = "http://147.93.130.237:8000/api/aircraft/ingest"
INGEST_SECRET_KEY = "t3l3m3try"
VERIFY_SSL        = False

DATA_DIR          = os.environ.get("DATA_DIR", "/home/titan5/projDir/data")
SPDB_AC_POSN_URL  = f"spdbp:://localhost::{DATA_DIR}/spdb/ac_posn"

# Path to SpdbQuery binary (try system PATH, then LROSE default)
LROSE_BIN         = os.environ.get("LROSE_BIN", "/usr/local/lrose/bin")
SPDB_QUERY_BIN    = os.path.join(LROSE_BIN, "SpdbQuery")

# How often to poll for new data (seconds)
POLL_INTERVAL     = 5

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

# Argentine sanity-check bounds
LAT_MIN, LAT_MAX = -55.0, -20.0
LON_MIN, LON_MAX = -75.0, -50.0


def run_spdb_query(n_secs_back: int = 30) -> str:
    """
    Run SpdbQuery and return its stdout output.
    Uses -mode latest -margin N to get the most recent position
    within the last n_secs_back seconds.

    URL can be a local path or spdbp:://host::dir.
    For local access, a plain directory path is simplest.
    """
    # For local filesystem access, use the directory path directly
    local_url = os.path.join(DATA_DIR, "spdb", "ac_posn")

    cmd = [
        SPDB_QUERY_BIN,
        "-url",    local_url,
        "-mode",   "latest",
        "-margin", str(n_secs_back),   # seconds back from now
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PATH": f"{LROSE_BIN}:{os.environ.get('PATH', '')}"},
        )
        if result.returncode != 0 and result.stderr:
            log.debug(f"SpdbQuery stderr: {result.stderr[:200]}")
        return result.stdout
    except FileNotFoundError:
        log.error(f"SpdbQuery no encontrado en {SPDB_QUERY_BIN}. Verificá LROSE_BIN.")
        return ""
    except subprocess.TimeoutExpired:
        log.warning("SpdbQuery timeout.")
        return ""
    except Exception as e:
        log.error(f"Error ejecutando SpdbQuery: {e}")
        return ""


def parse_spdb_output(output: str, seen: set) -> list[dict]:
    """
    Parse SpdbQuery output line-by-line for ac_posn_wmod_t structs.

    Confirmed format (from live SpdbQuery run):
        valid_time: 2026/02/22 19:52:14
        callsign: VBCT
          lat:  -34.59010
          lon:  -68.40450
          alt: 2461.00000
          gs: 0
          headingDeg: 0
    """
    aircraft_list = []

    valid_time_str = ""
    callsign_raw   = None
    lat = lon = alt_ft = gs_kt = heading = None

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Use split(":", 1) so values with colons aren't truncated
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()

        if key == "valid_time":
            # "2026/02/22 19:52:14" — keep latest seen before a callsign block
            valid_time_str = val
        elif key == "callsign":
            # Start of a new aircraft block — reset fields
            callsign_raw = val
            lat = lon = alt_ft = gs_kt = heading = None
        elif key == "lat":
            try: lat = float(val)
            except ValueError: pass
        elif key == "lon":
            try: lon = float(val)
            except ValueError: pass
        elif key == "alt":
            try: alt_ft = float(val)
            except ValueError: pass
        elif key == "gs":
            try: gs_kt = float(val)
            except ValueError: gs_kt = 0.0
        elif key == "headingdeg":
            try: heading = float(val)
            except ValueError: heading = 0.0
            # headingDeg is the last field in each block → try to emit
            if callsign_raw and lat is not None and lon is not None and alt_ft is not None:
                ac = _build_aircraft(
                    callsign_raw, lat, float(lon), float(alt_ft),
                    gs_kt or 0.0, heading or 0.0,
                    seen, valid_time_str,
                )
                if ac:
                    aircraft_list.append(ac)
            # Reset for next block
            callsign_raw = lat = lon = alt_ft = gs_kt = heading = None

    if not aircraft_list:
        log.info("⏳ Sin posiciones nuevas en este ciclo (sin datos o ya enviados).")

    return aircraft_list




def _build_aircraft(
    callsign_raw: str, lat: float, lon: float,
    alt_ft: float, speed_kt: float, heading: float,
    seen: set,
    valid_time_str: str = "",
) -> dict | None:
    """Validate and package an aircraft position."""
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None   # outside Argentina bounds

    dedup = (callsign_raw, round(lat, 4), round(lon, 4))
    if dedup in seen:
        return None
    # NOTE: do NOT add to seen here — only mark as seen after successful VPS send.
    # This ensures failed/timeout sends are retried on the next poll.

    # Use SPDB valid_time if available ("2026/02/22 19:52:14" → ISO 8601)
    if valid_time_str:
        try:
            t = time.strptime(valid_time_str, "%Y/%m/%d %H:%M:%S")
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
        except ValueError:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    else:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    reg = CALLSIGN_MAP.get(callsign_raw, callsign_raw)
    return {
        "callsign":  callsign_raw,
        "reg":       reg,
        "lat":       round(lat, 6),
        "lon":       round(lon, 6),
        "altitude":  round(alt_ft * 0.3048),   # ft → m
        "velocity":  round(speed_kt * 0.514444, 2),
        "heading":   round(heading),
        "timestamp": timestamp,
        "source":    "titan",
        "_dedup":    (callsign_raw, round(lat, 4), round(lon, 4)),  # used by caller
    }


def send_to_vps(aircraft: dict) -> bool:
    """POST aircraft position to VPS. Returns True on success."""
    payload = {k: v for k, v in aircraft.items() if k != "_dedup"}
    try:
        r = requests.post(
            VPS_API_URL,
            json=payload,
            headers={
                "X-Ingest-Key": INGEST_SECRET_KEY,
                "Content-Type": "application/json",
                "User-Agent":   "TitanStreamer/3.0",
            },
            timeout=15,        # increased from 5s — VPS can be slow
            verify=VERIFY_SSL,
        )
        if r.status_code == 200:
            log.info(f"✅ {aircraft['reg']} ({aircraft['lat']:.4f}, {aircraft['lon']:.4f})")
            return True
        else:
            log.warning(f"⚠️  VPS {r.status_code}: {r.text[:80]}")
            return False
    except requests.exceptions.ConnectionError:
        log.error("❌ Sin conexión al VPS.")
        return False
    except Exception as e:
        log.error(f"❌ Error HTTP: {e}")
        return False


def main() -> None:
    log.info("🛩️  TITAN Telemetry Streamer v3 (SpdbQuery) iniciado.")
    log.info(f"� VPS: {VPS_API_URL}")
    log.info(f"🗄️  SPDB: {SPDB_AC_POSN_URL}")

    # Quick sanity check
    if not os.path.isfile(SPDB_QUERY_BIN):
        log.error(f"SpdbQuery no encontrado: {SPDB_QUERY_BIN}")
        log.error("Verificá que LROSE esté instalado o exportá LROSE_BIN=/ruta/al/bin")
        return

    # Print SpdbQuery help to confirm it works (silent, just for startup check)
    test = subprocess.run([SPDB_QUERY_BIN, "-h"], capture_output=True, text=True, timeout=5)
    log.info(f"SpdbQuery disponible ✓ ({SPDB_QUERY_BIN})")

    seen: set[tuple] = set()   # persists across polls for de-duplication

    while True:
        output = run_spdb_query(n_secs_back=POLL_INTERVAL * 2)
        if output:
            log.info(f"📥 SpdbQuery: {len(output)} chars recibidos.")
            aircraft_list = parse_spdb_output(output, seen)
            for ac in aircraft_list:
                ok = send_to_vps(ac)
                if ok:
                    # Mark as seen only after successful send
                    seen.add(ac["_dedup"])
                    if len(seen) > 5000:
                        seen.clear()
        else:
            log.info("📭 SpdbQuery: sin output en este ciclo.")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
