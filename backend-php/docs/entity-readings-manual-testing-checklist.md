# Entity Readings Manual Testing Checklist

## Target story

- ISXI-280: retrieve measurements for any entity.

## Base URL

- `http://localhost:8001`

## Required AC checks

1. entity_id accepted as filter
- Request: `/readings?entity_id={{entity_id}}`
- Expect: `200` and JSON array

2. non-existent entity returns 404
- Request: `/readings?entity_id=9999999`
- Expect: `404`

3. returns measurements for all entity metrics
- Request: `/readings?entity_id={{entity_id}}`
- Expect: items include multiple metric_id values if entity has multiple metrics

4. combine entity filter with time range
- Request: `/readings?entity_id={{entity_id}}&start_time={{start_time}}&end_time={{end_time}}`
- Expect: all rows match entity and timestamps in range

5. response fields
- Expect each item includes:
  - `timestamp`
  - `value`
  - `metric_id`
  - `entity_id`

6. empty results return empty list
- Request with valid entity and old time range with no data
- Expect: `200` and `[]`

## Additional consistency checks

- `metric_id` + `entity_id` mismatch returns `400`.
- `start_time`/`end_time` invalid format returns `400`.
- reversed time range (`end_time < start_time`) returns `400`.
