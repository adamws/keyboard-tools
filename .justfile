# start docker containers with watch for source changes
# for automatic rebuilds enabled.
start-backend-dev:
  cd backend && \
    docker compose --profile monitor up --build --watch

# update server dependencies
update-backend-deps:
  cd backend && go get -u && go mod tidy

start-local-deployment:
  #!/usr/bin/env bash
  cd deploy && \
    source .env && docker compose up
