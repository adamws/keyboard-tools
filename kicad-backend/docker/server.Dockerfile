# Stage 1: Build Go binary
FROM golang:1.25-alpine AS builder

# Version argument for build-time injection
ARG VERSION=dev

WORKDIR /build

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build static binary with version information
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo \
    -ldflags "-X main.Version=${VERSION}" \
    -o kicad-server ./cmd/server

# Stage 2: Runtime
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/kicad-server /app/

# Expose server port
EXPOSE 8080

# Run server
CMD ["/app/kicad-server"]
