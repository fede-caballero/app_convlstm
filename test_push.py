import sys
sys.path.append('backend')
import logging
from pipeline_worker import check_and_send_aircraft_alerts
import aircraft_tracker

logging.basicConfig(level=logging.INFO)

# Inject mock plane
aircraft_tracker.update_local_aircraft({"reg": "TEST", "lat": -33.1, "lon": -68.4})

cache = {}
check_and_send_aircraft_alerts(cache)
