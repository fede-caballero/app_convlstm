#!/usr/bin/env python3
"""
Simulates TITAN SPDB ac_posn binary records for testing telemetry_streamer.py.

Creates a .data file with the same 96-byte record format and appends
new aircraft positions every few seconds, simulating real flight paths
around Mendoza.

Usage:
    python3 simulate_spdb.py [output_dir]

Default output_dir: /tmp/spdb_test/ac_posn
"""

import os
import sys
import struct
import time
import math
from datetime import date

RECORD_SIZE = 96
MISSING = -9999.0

# Simulated aircraft departing from San Rafael airport (SAMR: -34.5883, -68.4047)
# Coordinates confirmed from real VBCT telemetry: -34.5901, -68.4045
AIRCRAFT = [
    {"callsign": "VBCR", "center_lat": -34.5883, "center_lon": -68.4047, "radius": 0.18, "alt_ft": 8500,  "speed_kt": 180},
    {"callsign": "VBCT", "center_lat": -34.5883, "center_lon": -68.4047, "radius": 0.22, "alt_ft": 2461,  "speed_kt": 0},
    {"callsign": "VBCU", "center_lat": -34.5883, "center_lon": -68.4047, "radius": 0.14, "alt_ft": 5500,  "speed_kt": 140},
]


def make_record(callsign: str, lat: float, lon: float, heading: float, alt_ft: float, speed_kt: float) -> bytes:
    """Build a 96-byte SPDB ac_posn record (big-endian floats)."""
    buf = bytearray(RECORD_SIZE)

    # Offsets 0-11: lat, lon, heading (big-endian float32)
    struct.pack_into(">f", buf,  0, lat)
    struct.pack_into(">f", buf,  4, lon)
    struct.pack_into(">f", buf,  8, heading)

    # Offset 12: callsign (32 bytes, null-padded)
    cs_bytes = callsign.encode("ascii")[:32]
    buf[12:12 + len(cs_bytes)] = cs_bytes

    # Offset 44: altitude in feet
    struct.pack_into(">f", buf, 44, alt_ft)

    # Offset 48: ground speed in knots
    struct.pack_into(">f", buf, 48, speed_kt)

    # Fill remaining float slots with MISSING (-9999.0)
    for off in [52, 56, 60, 64, 68, 72, 76, 80, 84, 88, 92]:
        if off + 4 <= RECORD_SIZE:
            struct.pack_into(">f", buf, off, MISSING)

    return bytes(buf)


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/spdb_test/ac_posn"
    os.makedirs(output_dir, exist_ok=True)

    today = date.today().strftime("%Y%m%d")
    filepath = os.path.join(output_dir, f"{today}.data")

    print(f"✈️  Simulador SPDB binario iniciado.")
    print(f"📁 Escribiendo en: {filepath}")
    print(f"💡 En otra terminal, corré:")
    print(f"   DATA_DIR=/tmp/spdb_test python3 telemetry_streamer.py")
    print()

    step = 0
    with open(filepath, "ab") as f:
        while True:
            for ac in AIRCRAFT:
                # Circular orbit
                angle = math.radians(step * 5 + AIRCRAFT.index(ac) * 120)
                lat = ac["center_lat"] + ac["radius"] * math.sin(angle)
                lon = ac["center_lon"] + ac["radius"] * math.cos(angle)
                heading = (math.degrees(angle) + 90) % 360

                record = make_record(ac["callsign"], lat, lon, heading, ac["alt_ft"], ac["speed_kt"])
                f.write(record)
                f.flush()

                print(f"  📝 {ac['callsign']}: ({lat:.4f}, {lon:.4f}) hdg={heading:.0f}° alt={ac['alt_ft']}ft")

            step += 1
            print(f"  ⏳ Esperando 5s... (Ctrl+C para salir)\n")
            time.sleep(5)


if __name__ == "__main__":
    main()
