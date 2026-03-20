# ISXI-279 Manual Testing Checklist (Postman)

## Environment

- Base URL: `http://localhost:8000`
- Valid metric id: obtain from `GET /metrics?entity_id=<id>`

## Test Cases

1. Valid retrieval in time range
- Method: GET
- URL:
  - `/readings?metric_id={{metric_id}}&start_time=2026-03-18T10:00:00Z&end_time=2026-03-18T12:00:00Z&limit=10000`
- Expected:
  - Status `200`
  - Response is JSON array
  - Items contain `timestamp`, `value`, `metric_id`
  - Sorted ascending by `timestamp`

2. Metric not found
- Method: GET
- URL:
  - `/readings?metric_id=9999999&start_time=2026-03-18T10:00:00Z&end_time=2026-03-18T12:00:00Z`
- Expected:
  - Status `404`
  - Response contains `error.status`, `error.message`, `error.path`

3. Invalid timestamp format
- Method: GET
- URL:
  - `/readings?metric_id={{metric_id}}&start_time=not-a-date&end_time=2026-03-18T12:00:00Z`
- Expected:
  - Status `400`
  - Response contains `error.status`, `error.message`, `error.path`

4. Reversed timestamps
- Method: GET
- URL:
  - `/readings?metric_id={{metric_id}}&start_time=2026-03-18T12:00:00Z&end_time=2026-03-18T10:00:00Z`
- Expected:
  - Status `400`

5. Empty result list (no data)
- Method: GET
- URL:
  - `/readings?metric_id={{metric_id}}&start_time=2000-01-01T00:00:00Z&end_time=2000-01-01T01:00:00Z`
- Expected:
  - Status `200`
  - Response `[]`

6. High limit performance smoke check
- Method: GET
- URL:
  - `/readings?metric_id={{metric_id}}&start_time=2026-03-17T00:00:00Z&end_time=2026-03-18T23:59:59Z&limit=10000`
- Expected:
  - Status `200`
  - Endpoint remains responsive for practical demo usage

## Notes

- Global error format is standardized for raised HTTP errors:
  - `{"error": {"status": <int>, "message": <string>, "path": <string>}}`
- Swagger UI is available at `/docs`.
