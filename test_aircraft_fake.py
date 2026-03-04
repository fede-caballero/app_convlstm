import sys
sys.path.append('backend')
from aircraft_tracker import update_local_aircraft
update_local_aircraft({"callsign": "FAKE", "lat": -34.500, "lon": -68.300, "heading": 90.0})
