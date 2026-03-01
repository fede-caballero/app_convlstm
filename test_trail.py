import sys
sys.path.append('backend')
import aircraft_tracker

# First update
aircraft_tracker.update_local_aircraft({"reg": "LV-BCT", "lat": -33.1, "lon": -68.4})
print("Frame 1:", len(aircraft_tracker.get_aircraft_data()))

# Second update
aircraft_tracker.update_local_aircraft({"reg": "LV-BCT", "lat": -33.2, "lon": -68.5})
print("Frame 2:", len(aircraft_tracker.get_aircraft_data()))
