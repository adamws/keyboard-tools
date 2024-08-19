FROM node:22.6.0-alpine3.20 AS JS_BUILD
RUN apk add --no-cache git
COPY webapp /webapp
WORKDIR webapp

RUN npm install --unsafe-perm && npm run build

FROM golang:1.23.0-alpine3.20 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.20.0
COPY --from=JS_BUILD /webapp/dist* ./webapp/
COPY --from=GO_BUILD /go/bin/server ./
EXPOSE 8080
CMD ./server
