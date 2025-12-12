FROM node:22.6.0-alpine3.20 AS LANDING_BUILD
RUN apk add --no-cache git
COPY frontend/landing-page /landing-page
WORKDIR landing-page

RUN npm install && npm run build

FROM golang:1.24.1-alpine3.21 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.21.3
COPY --from=LANDING_BUILD /landing-page/dist* ./landing-page/
COPY --from=GO_BUILD /go/bin/server ./
EXPOSE 8080
CMD ./server
