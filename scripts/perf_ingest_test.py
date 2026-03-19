#!/usr/bin/env python3
"""
Performance test: send 500 measurements in a single POST to /ingest and assert <5s

Usage (from repo root):
  python scripts/perf_ingest_test.py

This script requires `docker` and `docker compose` available on the host where it's run.
It talks to the DB container to obtain a zone and metric ids, posts to the PHP service
on localhost:8001 (docker-compose port mapping), and measures memory of the
`project-nexus-backend-php` container via `docker stats --no-stream`.
"""
import json
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def docker_psql(query):
    cmd = f"docker compose exec -T db psql -U nexus_dev -d projectnexus -t -c \"{query}\""
    rc, out, err = run(cmd)
    if rc != 0:
        raise RuntimeError(f"psql failed: {err}")
    return out.strip()


def get_backend_mem():
    # Returns memory usage in bytes for project-nexus-backend-php
    cmd = "docker stats --no-stream --format '{{.MemUsage}}' project-nexus-backend-php"
    rc, out, err = run(cmd)
    if rc != 0:
        raise RuntimeError(f"docker stats failed: {err}")
    # out example: '23.5MiB / 1.944GiB'
    part = out.split('/')[0].strip()
    # numeric + unit
    num = ''.join(ch for ch in part if (ch.isdigit() or ch == '.' ))
    unit = ''.join(ch for ch in part if (ch.isalpha() or ch == '%'))
    factor = 1
    u = unit.lower()
    if 'g' in u:
        factor = 1024 ** 3
    elif 'm' in u:
        factor = 1024 ** 2
    elif 'k' in u:
        factor = 1024
    try:
        return int(float(num) * factor)
    except Exception:
        raise RuntimeError(f"failed to parse memory string: {out}")


def post_ingest(url, readings, timeout=30):
    data = json.dumps(readings).encode('utf-8')
    req = Request(url, data=data, headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            elapsed = time.monotonic() - start
            return resp.getcode(), body, elapsed
    except HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore'), time.monotonic() - start
    except URLError as e:
        raise


def main():
    print('Collecting zone and metric ids from DB...')
    zone = docker_psql('SELECT id FROM zones LIMIT 1;')
    if not zone:
        print('No zone found; please run the simulator bootstrap first.', file=sys.stderr)
        sys.exit(2)
    zone_id = int(zone.strip())
    metrics_out = docker_psql('SELECT id FROM metrics LIMIT 10;')
    metric_ids = [int(x) for x in metrics_out.splitlines() if x.strip()]
    if not metric_ids:
        print('No metrics found; please run the simulator bootstrap first.', file=sys.stderr)
        sys.exit(2)

    N = 500
    readings = []
    from random import choice, uniform
    from datetime import datetime, timezone
    for i in range(N):
        readings.append({
            'entity_id': zone_id,
            'metric_id': choice(metric_ids),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'value': round(20.0 + uniform(-5, 5), 2),
        })

    url = 'http://localhost:8001/ingest'

    print('Measuring backend memory (before)...')
    mem_before = get_backend_mem()
    print(f' backend mem: {mem_before / (1024*1024):.2f} MiB')

    print(f'Sending {N} readings to {url} ...')
    code, body, elapsed = post_ingest(url, readings, timeout=30)
    print('Response code:', code)
    print('Response body:', (body[:400] + '...') if len(body) > 400 else body)
    print(f'Elapsed: {elapsed:.3f}s')

    print('Measuring backend memory (after)...')
    mem_after = get_backend_mem()
    print(f' backend mem: {mem_after / (1024*1024):.2f} MiB')

    mem_diff = mem_after - mem_before
    print(f'Memory delta: {mem_diff / (1024*1024):.2f} MiB')

    passed = True
    if elapsed > 5.0:
        print(f'FAIL: elapsed {elapsed:.3f}s > 5.0s')
        passed = False
    else:
        print(f'PASS: elapsed {elapsed:.3f}s <= 5.0s')

    # flag if memory increased more than 200MB
    THRESHOLD = 200 * 1024 * 1024
    if mem_diff > THRESHOLD:
        print(f'FAIL: memory increased by {mem_diff/(1024*1024):.2f} MiB > threshold {(THRESHOLD/(1024*1024))} MiB')
        passed = False
    else:
        print(f'PASS: memory increase {mem_diff/(1024*1024):.2f} MiB <= threshold {(THRESHOLD/(1024*1024))} MiB')

    if not passed:
        sys.exit(1)
    print('Performance test passed')


if __name__ == '__main__':
    main()
