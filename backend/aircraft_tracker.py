
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
    "lv-bcu": {"reg": "LV-BCU", "type": "T-MaybeSeed"}, # Filter by Callsign
    "lq-bcr": {"reg": "LQ-BCR", "type": "T-MaybeSeed"},  # Filter by Callsign
    "lq-bcp": {"reg": "LQ-BCP", "type": "T-MaybeSeed"}, # From research
    "lq-bcu": {"reg": "LQ-BCU", "type": "T-MaybeSeed"}, # From research
}

# Cache to avoid hitting rate limits (OpenSky Free = 10s for anon, though we'll query every 30s)
_cache = {
    "last_update": 0,
    "data": []
}

def get_aircraft_data():
    now = time.time()
    if now - _cache["last_update"] < 15: # 15s cache
        return _cache["data"]

    try:
        # Construct params
        params = BBOX.copy()
        
        # We can't filter by icao24 AND bounding box easily in one query without own account sometimes,
        # but let's try basic BBOX query which is standard.
        response = requests.get(OPENSKY_URL, params=params, timeout=5)
        
        if response.status_code == 200:
            raw_data = response.json()
            states = raw_data.get("states", [])
            
            filtered_aircraft = []
            
            if states:
                for s in states:
                    # s structure: [icao24, callsign, origin_country, time_position, last_contact, long, lat, baro_altitude, on_ground, velocity, true_track, vertical_rate, sensors, geo_altitude, squawk, spi, position_source]
                    
                    icao24 = s[0].lower() if s[0] else ""
                    callsign = s[1].strip().lower() if s[1] else ""
                    lat = s[6]
                    lon = s[5]
                    heading = s[10]
                    
                    if not lat or not lon:
                        continue

                    # Check match
                    matched_info = None
                    
                    # 1. Check ICAO Hex
                    if icao24 in TRACKED_AIRCRAFT:
                         matched_info = TRACKED_AIRCRAFT[icao24]
                    
                    # 2. Check Callsign (contains)
                    if not matched_info:
                        for key, info in TRACKED_AIRCRAFT.items():
                            # key could be "lv-bcu"
                            if key in callsign:
                                matched_info = info
                                break
                    
                    if matched_info:
                        filtered_aircraft.append({
                            "icao24": icao24,
                            "callsign": s[1].strip(), # Original Case
                            "reg": matched_info["reg"],
                            "lat": lat,
                            "lon": lon,
                            "heading": heading,
                            "altitude": s[7], # Barometric
                            "velocity": s[9],
                            "on_ground": s[8]
                        })

            _cache["data"] = filtered_aircraft
            _cache["last_update"] = now
            return filtered_aircraft
            
        else:
            logging.error(f"OpenSky API Error: {response.status_code}")
            return _cache["data"] # Return stale data on error

    except Exception as e:
        logging.error(f"Error fetching aircraft data: {e}")
        return _cache["data"]
