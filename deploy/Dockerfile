FROM node:22.6.0-alpine3.20 AS LANDING_BUILD
RUN apk add --no-cache git
COPY frontend/landing-page /landing-page
WORKDIR landing-page

RUN npm install && npm run build

FROM lipanski/docker-static-website:2.6.0
COPY --from=LANDING_BUILD /landing-page/dist* .
