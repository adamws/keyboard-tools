# Tests

## Running Tests with Docker

The test setup uses the modified copy of production docker-compose configuration.

### Start Services

From the `tests` directory, run:

```bash
# Build all services
docker compose build

# Start all services (includes selenium)
DOMAIN=localhost docker compose up -d
```

This starts:
- **kicad-app** service at `http://kicad.localhost:8080` (KiCad application)
- **Main domain** at `http://localhost:8080` (landing page)
- **Selenium Firefox** at `localhost:7900` (VNC viewer, password: `secret`)
- All backend services (worker, redis, minio)

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
- **Frontend**: `http://kicad.localhost` (selenium accesses the KiCad app)
- **Backend API**: `http://kicad.localhost` (direct API testing)

## Local Development Testing

You can also test only with worker dockerized and other services running locally:

```bash
# In separate terminals:
# 1. Start backend
cd server && go run server.go

# 2. Start frontend
cd frontend/kicad-app && npm run dev

# 3. Start worker
cd kicad-api && docker compose build && docker compose up

# 4. Run tests with custom URLs
pytest --webdriver=firefox --website-selenium=http://localhost:<frontend port> --backend-test-host=http://localhost:8080
```
