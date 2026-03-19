#!/usr/bin/env python3
import json
from datetime import datetime, timezone
import requests

URL = 'http://backend_php:8000/ingest'

# 1) Invalid IDs test
bad_payload = [{'entity_id': 999999999,'metric_id': 999999999,'timestamp': datetime.now(timezone.utc).isoformat(),'value': 1.23}]
try:
    r = requests.post(URL, json=bad_payload, timeout=10)
    print('INVALID_TEST_STATUS', r.status_code)
    print('INVALID_TEST_BODY', r.text)
except Exception as e:
    print('INVALID_TEST_EXCEPTION', str(e))

# 2) Bootstrap and valid post
from simulator import wait_for_db, bootstrap, wait_for_api, normal_value
conn = wait_for_db()
zone_id, metric_ids = bootstrap(conn)
conn.close()
wait_for_api()
metric_id = list(metric_ids.values())[0]
metric_name = list(metric_ids.keys())[0]
reading = {'entity_id': zone_id, 'metric_id': metric_id, 'timestamp': datetime.now(timezone.utc).isoformat(), 'value': normal_value(metric_name)}
try:
    r2 = requests.post(URL, json=[reading], timeout=10)
    print('VALID_TEST_STATUS', r2.status_code)
    print('VALID_TEST_BODY', r2.text)
except Exception as e:
    print('VALID_TEST_EXCEPTION', str(e))
