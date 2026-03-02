import time
import logging

# Target Aircraft
# Dict mapping identifier (ICAO or Callsign) to details
TRACKED_AIRCRAFT = {
    "e020d4": {"reg": "LV-BCT", "type": "T-MaybeSeed"}, # Known Hex
    "e020d2": {"reg": "LV-BCR", "type": "T-MaybeSeed"}, # Known Hex
    "lv-bcu": {"reg": "LV-BCU", "type": "T-MaybeSeed"}, # Filter by Callsign
    "lq-bcu": {"reg": "LQ-BCU", "type": "T-MaybeSeed"}, # No ADS-B Out likely, but keeping fallback
    "lq-bcp": {"reg": "LQ-BCP", "type": "T-MaybeSeed"}, 
}

# Local (TITAN) telemetry cache: keyed by callsign, expires in 30s if no update
_local_cache: dict[str, dict] = {}
LOCAL_TTL_SECONDS = 30  # If no update for 30s, consider the aircraft gone

# Trail history
MAX_TRAIL_POINTS = 50
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
    local_data = _get_local_aircraft()
    
    # Update and attach trails
    for ac in local_data:
        reg = ac.get("reg", ac.get("callsign"))
        if not reg: continue
        
        if "reg" not in ac:
            ac["reg"] = reg
        
        if reg not in _trail_cache:
            _trail_cache[reg] = []
            
        last_pt = _trail_cache[reg][-1] if _trail_cache[reg] else None
        if not last_pt or last_pt[1] != ac["lat"] or last_pt[0] != ac["lon"]:
            _trail_cache[reg].append([ac["lon"], ac["lat"]])
            if len(_trail_cache[reg]) > MAX_TRAIL_POINTS:
                _trail_cache[reg] = _trail_cache[reg][-MAX_TRAIL_POINTS:]
                
        ac["trail"] = _trail_cache[reg]

    return local_data
