
import requests
import time
import logging

# Configuration
OPENSKY_URL = "https://opensky-network.org/api/states/all"
# Mendoza Bounding Box (Approximate to cover operation area)
# Lat: -36 to -32, Lon: -70 to -66
BBOX = {"lamin": -36.0, "lomin": -70.5, "lamax": -31.5, "lomax": -66.0}

# Target Aircraft
# Dict mapping identifier (ICAO or Callsign) to details
TRACKED_AIRCRAFT = {
    "e020d4": {"reg": "LV-BCT", "type": "T-MaybeSeed"}, # Known Hex
    "e020d2": {"reg": "LV-BCR", "type": "T-MaybeSeed"}, # Known Hex
    "lv-bcu": {"reg": "LV-BCU", "type": "T-MaybeSeed"}, # Filter by Callsign
    "lq-bcu": {"reg": "LQ-BCU", "type": "T-MaybeSeed"}, # No ADS-B Out likely, but keeping fallback
    "lq-bcp": {"reg": "LQ-BCP", "type": "T-MaybeSeed"}, 
}

# OpenSky result cache (15s TTL to respect rate limits)
_opensky_cache = {
    "last_update": 0,
    "data": []
}

# Local (TITAN) telemetry cache: keyed by callsign, expires in 30s if no update
_local_cache: dict[str, dict] = {}
LOCAL_TTL_SECONDS = 30  # If no update for 30s, consider the aircraft gone

# Trail history
MAX_TRAIL_POINTS = 70
_trail_cache: dict[str, list] = {}  # reg -> [[lon, lat], ...]


def update_local_aircraft(aircraft: dict):
    """Called by the /api/aircraft/ingest endpoint when a new position arrives."""
    key = aircraft.get("callsign", aircraft.get("reg", "unknown"))
    aircraft["_received_at"] = time.time()
    _local_cache[key] = aircraft
    logging.info(f"[TITAN] Position updated: {key} @ ({aircraft.get('lat')}, {aircraft.get('lon')})")


def _get_local_aircraft() -> list[dict]:
    """Returns fresh local aircraft, removing stale entries."""
    now = time.time()
    fresh = []
    stale_keys = []
    for key, ac in _local_cache.items():
        age = now - ac.get("_received_at", 0)
        if age <= LOCAL_TTL_SECONDS:
            entry = {k: v for k, v in ac.items() if k != "_received_at"}
            entry["source"] = "titan"
            fresh.append(entry)
        else:
            stale_keys.append(key)
    for k in stale_keys:
        del _local_cache[k]
        logging.info(f"[TITAN] Removed stale aircraft: {k}")
    return fresh


def get_aircraft_data():
    now = time.time()

    # Refresh OpenSky cache if stale
    if now - _opensky_cache["last_update"] >= 15:
        try:
            params = BBOX.copy()
            response = requests.get(OPENSKY_URL, params=params, timeout=5)
            
            if response.status_code == 200:
                raw_data = response.json()
                states = raw_data.get("states", []) or []
                
                filtered_aircraft = []
                for s in states:
                    icao24 = s[0].lower() if s[0] else ""
                    callsign = s[1].strip().lower() if s[1] else ""
                    lat = s[6]
                    lon = s[5]
                    heading = s[10]
                    
                    if not lat or not lon:
                        continue

                    matched_info = None
                    
                    # 1. Check ICAO Hex
                    if icao24 in TRACKED_AIRCRAFT:
                        matched_info = TRACKED_AIRCRAFT[icao24]
                    
                    # 2. Check Callsign (contains)
                    if not matched_info:
                        for key, info in TRACKED_AIRCRAFT.items():
                            if key in callsign:
                                matched_info = info
                                break
                    
                    if matched_info:
                        filtered_aircraft.append({
                            "icao24": icao24,
                            "callsign": s[1].strip(),
                            "reg": matched_info["reg"],
                            "lat": lat,
                            "lon": lon,
                            "heading": heading,
                            "altitude": s[7],  # Barometric (meters)
                            "velocity": s[9],
                            "on_ground": s[8],
                            "source": "opensky"
                        })

                _opensky_cache["data"] = filtered_aircraft
                _opensky_cache["last_update"] = now
            else:
                logging.error(f"OpenSky API Error: {response.status_code}")

        except Exception as e:
            logging.error(f"Error fetching aircraft data from OpenSky: {e}")

    local_data = _get_local_aircraft()
    local_regs = {ac.get("reg", ac.get("callsign")) for ac in local_data}

    # Add OpenSky planes that are NOT already tracked locally
    opensky_unique = [
        ac for ac in _opensky_cache["data"]
        if ac.get("reg") not in local_regs
    ]

    merged_data = local_data + opensky_unique
    
    # Update and attach trails
    for ac in merged_data:
        reg = ac.get("reg", ac.get("callsign"))
        if not reg: continue
        
        if "reg" not in ac:
            ac["reg"] = reg
        
        if reg not in _trail_cache:
            _trail_cache[reg] = []
            
        last_pt = _trail_cache[reg][-1] if _trail_cache[reg] else None
        if not last_pt or last_pt["lat"] != ac["lat"] or last_pt["lon"] != ac["lon"]:
            _trail_cache[reg].append([ac["lon"], ac["lat"]])
            if len(_trail_cache[reg]) > MAX_TRAIL_POINTS:
                _trail_cache[reg] = _trail_cache[reg][-MAX_TRAIL_POINTS:]
                
        ac["trail"] = _trail_cache[reg]

    return merged_data
