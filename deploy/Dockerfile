FROM node:20.5.1-alpine3.17 AS JS_BUILD
RUN apk add --no-cache git
COPY webapp /webapp
WORKDIR webapp

RUN npm install --unsafe-perm && npm run build

FROM golang:1.21.0-alpine3.17 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.17.0
COPY --from=JS_BUILD /webapp/dist* ./webapp/
COPY --from=GO_BUILD /go/bin/server ./
EXPOSE 8080
CMD ./server
