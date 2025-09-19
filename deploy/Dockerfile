FROM node:22.6.0-alpine3.20 AS JS_BUILD
RUN apk add --no-cache git
COPY frontend/kicad-app /kicad-app
WORKDIR kicad-app

RUN npm install --unsafe-perm && npm run build

FROM node:22.6.0-alpine3.20 AS LANDING_BUILD
RUN apk add --no-cache git
COPY frontend/landing-page /landing-page
WORKDIR landing-page

RUN npm install && npm run build

FROM node:22.6.0-alpine3.20 AS DOCS_BUILD
RUN apk add --no-cache git
COPY docs /docs
WORKDIR docs

RUN npm install && npm run docs:build

FROM golang:1.24.1-alpine3.21 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.21.3
COPY --from=JS_BUILD /kicad-app/dist* ./kicad-app/
COPY --from=LANDING_BUILD /landing-page/dist* ./landing-page/
COPY --from=DOCS_BUILD /docs/src/.vitepress/dist* ./docs/
COPY --from=GO_BUILD /go/bin/server ./
EXPOSE 8080
CMD ./server
