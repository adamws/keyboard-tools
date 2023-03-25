# Tests

There are multiple ways to run tests. First you need to start all services.
You can do this with `docker-compose` by running following commands inside `tests` directory:

```
docker-compose -f docker-compose.yml -f ../kicad-api/docker-compose.yml -f docker-compose.override.yml build
docker-compose -f docker-compose.yml -f ../kicad-api/docker-compose.yml -f docker-compose.override.yml up
```

This will start website backend, kicad worker and selenium worker with all other required dependencies.
Selenium can be previewed at `localhost:7900` (using default password: `secret`).
Then, start pytest. It is recommended to use `venv` for managing dependencies. For example:

```
python -m venv .env
. .env/bin/activate
pip install -r requirements.txt
pytest
```

You can also test without docker (only `firefox` selenium driver supported for now).
Instead of running `docker-compose up` start services locally and run `pytest` with additional arguments.
For example when running backend with `go run kle-app` and frontend with `npm run dev`:

```
pytest --webdriver=firefox --website-selenium=http://localhost:5173 --backend-test-host=http://localhost:8080
```
