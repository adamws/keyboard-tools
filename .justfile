# start docker containers with watch for source changes
# for automatic rebuilds enabled.
start-kicad-backend-dev:
  cd kicad-backend && \
    docker compose --profile monitor up --build --watch

# update server dependencies
update-kicad-backend-deps:
  cd kicad-backend && go get -u && go mod tidy

start-local-deployment:
  #!/usr/bin/env bash
  cd deploy && \
    source .env && docker compose up
