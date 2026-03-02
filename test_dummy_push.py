import sys
import os
import json
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append('backend')
from pipeline_worker import check_and_send_aircraft_alerts, DB_PATH
import aircraft_tracker

if not os.path.exists(DB_PATH):
    print(f"Error: Database file not found at {DB_PATH}")

aircraft_tracker.update_local_aircraft({"callsign": "VBCT", "lat": -34.5, "lon": -68.3})

# Fake RAM state dictionary
sent_aircraft_alerts = {}

# Trigger push function
check_and_send_aircraft_alerts(sent_aircraft_alerts)

print("Execution Finished.")
