# Tests

## Running Tests with Docker

The test setup uses the modified copy of production docker-compose configuration.

### Start Services

From the `tests` directory, run:

```bash
# Build all services
docker compose build

# Start all services
DOMAIN=localhost docker compose up -d
```

This starts:
- **kicad-app** service at `http://kicad.localhost:8080` (KiCad application)
- **Main domain** at `http://localhost:8080` (landing page)
- All backend services (worker, redis, seaweedfs)

### Run Tests

Set up Python environment and run pytest:

```bash
python -m venv .env
. .env/bin/activate
pip install -r requirements.txt
pytest
```

### Configuration

The tests use these URLs by default:
- **Backend API**: `http://kicad.localhost` (direct API testing)

## Local Development Testing

You can also test only with worker dockerized and other services running locally:

```bash
# In separate terminals:
# 1. Start backend
cd server && go run server.go

# 2. Start worker
cd kicad-api && docker compose build && docker compose up

# 3. Run tests with custom URLs
pytest --webdriver=firefox --backend-test-host=http://localhost:8080
```
