import time
import logging

# Target Aircraft
# Dict mapping identifier (ICAO or Callsign) to details
TRACKED_AIRCRAFT = {
    "e020d4": {"reg": "LV-BCT", "type": "T-MaybeSeed"}, # Known Hex
    "e020d2": {"reg": "LV-BCR", "type": "T-MaybeSeed"}, # Known Hex
    "lv-bcu": {"reg": "LV-BCU", "type": "T-MaybeSeed"}, # Filter by Callsign
    "lq-bcu": {"reg": "LQ-BCU", "type": "T-MaybeSeed"}, # No ADS-B Out likely, but keeping fallback
}
import time
import logging

from database import get_db_connection

# Trail history (still OK in memory since only the API reader displays it)
MAX_TRAIL_POINTS = 50
_trail_cache: dict[str, list] = {}  # reg -> [[lon, lat], ...]

def _init_aircraft_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_aircraft (
            callsign TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            heading REAL,
            received_at REAL
        )
    ''')
    conn.commit()
    conn.close()

# Ensure table exists on import
_init_aircraft_db()

def update_local_aircraft(aircraft: dict):
    """Called by the /api/aircraft/ingest endpoint when a new position arrives."""
    key = aircraft.get("callsign", aircraft.get("reg", "unknown"))
    lat = aircraft.get("lat")
    lon = aircraft.get("lon")
    heading = aircraft.get("heading", 0.0)
    now = time.time()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO active_aircraft (callsign, lat, lon, heading, received_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(callsign) DO UPDATE SET 
            lat=excluded.lat, 
            lon=excluded.lon, 
            heading=excluded.heading, 
            received_at=excluded.received_at
    """, (key, lat, lon, heading, now))
    conn.commit()
    conn.close()
    
    logging.info(f"[TITAN] Database position updated: {key} @ ({lat}, {lon})")

def _get_local_aircraft() -> list[dict]:
    """Returns fresh local aircraft from SQLite, removing stale entries."""
    now = time.time()
    cutoff_time = now - 30  # 30 seconds TTL
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete stale first
    cursor.execute("DELETE FROM active_aircraft WHERE received_at < ?", (cutoff_time,))
    if cursor.rowcount > 0:
        logging.info(f"[TITAN] Removed {cursor.rowcount} stale aircraft from database.")
    conn.commit()
    
    # Fetch active
    cursor.execute("SELECT callsign, lat, lon, heading FROM active_aircraft")
    rows = cursor.fetchall()
    conn.close()
    
    fresh = []
    for row in rows:
        fresh.append({
            "callsign": row[0],
            "reg": row[0], # fallback
            "lat": row[1],
            "lon": row[2],
            "heading": row[3],
            "source": "titan"
        })
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
