# Testing deployment locally

Run

``` bash
docker compose up
```

Application will be accessible at `https://localhost`.
For local runs it is impossible to get trusted certificate so traefik will generate default, self signed certificate.
Your browser will warn you about security risk. This can be safely ignored.

# Deployment on server

In order to deploy on server set environment variables (in `.env` file):

```
ACME_EMAIL=<email to be used for certificate registration>
DOMAIN=<domain poiting to server>
```

and run:

```
docker compose up
```

Traefik will also expose other services:

- `https://prometheus.localhost` - default credentials: `user:secret`
