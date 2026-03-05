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