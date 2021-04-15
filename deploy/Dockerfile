FROM node:15.14.0-alpine3.12 AS JS_BUILD
RUN apk add --no-cache git
COPY webapp /webapp
WORKDIR webapp

RUN npm install --unsafe-perm && npm run build

FROM golang:1.16.3-alpine3.12 AS GO_BUILD
COPY server /server
WORKDIR /server
RUN go build -o /go/bin/server

FROM alpine:3.12.0
COPY --from=JS_BUILD /webapp/build* ./webapp/
COPY --from=GO_BUILD /go/bin/server ./
CMD ./server
