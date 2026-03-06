# Project Nexus

## Getting started

1. Install Docker Desktop.
2. Start the stack:

```bash
docker compose up --build
```

## Services & Ports

Once the Docker stack starts, you can access the following services:

- **Frontend Dashboard (React)**: [http://localhost:3000](http://localhost:3000)
- **PHP Backend**: [http://localhost:8000](http://localhost:8000)
- **Python Backend (FastAPI)**: [http://localhost:8001](http://localhost:8001)
- **TimescaleDB (PostgreSQL)**: `localhost:5432` (Login: `nexususer` / `nexuspass`)

## Database details & persistence

- The project uses TimescaleDB (a PostgreSQL distribution with time-series extensions). The Compose service is `timescale/timescaledb:latest-pg16` so this is not MySQL.
- Data is persisted to a Docker volume (look for a volume named like `project-nexus_timescaledb_data`). The Postgres data directory is mounted at `/var/lib/postgresql/data` inside the container.

How init scripts work
- The folder `./sql` is mounted into the container's `/docker-entrypoint-initdb.d`. Any `*.sql` files there will run only when the database is first initialized (i.e., when the data directory is empty). That means the `sql/001_init_schema.sql` file will create tables and insert seed rows only on first startup.

Why you may lose data
- If you recreate the database container but reuse the same Docker volume, your data will stay intact.
- If you remove the Docker volume (or Docker Compose is run on a different machine or project name), the data directory will be empty and the init scripts will run again — or if the init scripts do not include full seeding of `sensor_readings`, you may see no sample readings.

Useful commands
- List volumes:
	- `docker volume ls`
- Inspect the project volume (replace name shown by `docker volume ls`):
	- `docker volume inspect project-nexus_timescaledb_data`
- Connect to the DB with psql (from host, if port mapped):
	- `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB`
- Show tables / data:
	- `SELECT table_name FROM information_schema.tables WHERE table_schema='public';`
	- `SELECT id,name FROM zones ORDER BY id;`
	- `SELECT count(*) FROM sensor_readings;`
- Seed sample readings (one-off, from host):
	- `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "INSERT INTO sensor_readings (zone_id,timestamp,temperature,humidity) SELECT 1, (now() - interval '24 hours') + (g * interval '1 hour'), round((20 + random()*4)::numeric,1), round((50 + random()*8)::numeric,1) FROM generate_series(0,23) AS g;"`
- To force the init scripts to re-run (WARNING: this deletes all DB data):
	1. `docker compose down`
 2. Remove the volume: `docker volume rm project-nexus_timescaledb_data`
 3. `docker compose up --build` (the `./sql/*.sql` files will run on first init)

Backups
- Use `pg_dump` to export data before removing volumes:
	- `docker compose exec db pg_dump -U $POSTGRES_USER -d $POSTGRES_DB > backup.sql`

If you want I can:
- Add a small admin endpoint to the backend to (re)seed sample readings on demand, or
- Add an idempotent seeding step into `sql/001_init_schema.sql` so sensor readings are present on fresh volumes.

Idempotent seeding
- The `sql/001_init_schema.sql` file now includes an idempotent seeding step: when the database is initialized (or when the init scripts run) it will insert sample `sensor_readings` only if the `sensor_readings` table is empty. This prevents duplicate data if the init scripts are applied multiple times and makes it safe to recreate the database during development.

Notes
- If you want to force a fresh initialization (and run the init scripts from scratch), you must remove the DB Docker volume first (see steps above). Otherwise the init scripts will be skipped because the DB data directory is present.
