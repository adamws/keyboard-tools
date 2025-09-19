FROM node:22.6.0-alpine3.20 AS JS_BUILD
RUN apk add --no-cache git
COPY frontend/kicad-app /kicad-app
WORKDIR kicad-app

RUN npm install --unsafe-perm && npm run build

FROM golang:1.24.1-alpine3.21 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.21.3
COPY --from=JS_BUILD /kicad-app/dist* ./kicad-app/
COPY --from=GO_BUILD /go/bin/server ./
EXPOSE 8080
CMD ./server
