# Manual Test Cases for GET /readings

## Valid metric_id
- Request: GET /readings?metric_id=1
- Expected: 200 OK with readings data, including is_anomaly field

## Invalid metric_id
- Request: GET /readings?metric_id=999
- Expected: 404 Not Found with message "metric_id 999 not found."

## Invalid start
- Request: GET /readings?metric_id=1&start=invalid-date
- Expected: 400 Bad Request with message "Invalid start: 'invalid-date'. Use ISO 8601 format."

## Invalid end
- Request: GET /readings?metric_id=1&end=invalid-date
- Expected: 400 Bad Request with message "Invalid end: 'invalid-date'. Use ISO 8601 format."

## start >= end
- Request: GET /readings?metric_id=1&start=2023-01-01T00:00:00&end=2023-01-01T00:00:00
- Expected: 400 Bad Request with message "'start' must be before 'end'"

## No readings found
- Request: GET /readings?metric_id=1&start=2020-01-01T00:00:00&end=2020-01-02T00:00:00
- Expected: 200 OK with empty readings array

## Anomaly flag present in /readings response
- Request: GET /readings?metric_id=1
- Expected: Each reading object includes "is_anomaly": true/false