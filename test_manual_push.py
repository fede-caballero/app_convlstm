import sys, os, json, logging, time
import sqlite3
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
sys.path.append(os.path.abspath('backend'))

from backend import aircraft_tracker

print(f"Fetching manually... {datetime.now(timezone.utc)}")
data = aircraft_tracker.get_aircraft_data()
print("DATA RETURNED:", data)

from backend.pipeline_worker import check_and_send_aircraft_alerts

sent_aircraft_alerts = {}
check_and_send_aircraft_alerts(sent_aircraft_alerts)

print("Push Test Completed.")
