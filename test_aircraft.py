import sys
sys.path.append('backend')
import aircraft_tracker

aircraft_tracker.update_local_aircraft({"callsign": "LV-ABC", "lat": -33.1, "lon": -68.4})
print(aircraft_tracker.get_aircraft_data())
