# Stage 1: Build Go binary
FROM golang:1.25-alpine AS builder

WORKDIR /build

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build static binary (CGO_ENABLED=0 for portability)
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o kicad-worker ./cmd/worker

# Stage 2: Runtime with KiCad
FROM admwscki/kicad-kbplacer-primary:9.0.6-noble

# Remove default user, create kicad user
RUN userdel -r ubuntu

ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID -o kicad \
  && useradd -u $UID -g $GID --create-home --shell /bin/bash kicad \
  && usermod -m -d /kicad kicad

USER kicad
WORKDIR /kicad

ARG PLUGINS_PATH=/kicad/.local/share/kicad/9.0/3rdparty/plugins
RUN mkdir -p $PLUGINS_PATH

ENV PATH="/kicad/.local/bin:${PATH}"

# Install keyswitch footprints (same as before)
RUN cd /kicad/.local/share/kicad/9.0/3rdparty \
  && mkdir -p footprints \
  && mkdir tmp && cd tmp \
  && wget https://github.com/kiswitch/keyswitch-kicad-library/releases/download/v2.4/keyswitch-kicad-library.zip \
  && echo "b38d56323acb91ad660567340ca938c5b4a83a27eea52308ef14aa7857b0071b keyswitch-kicad-library.zip" | sha256sum -c \
  && unzip keyswitch-kicad-library.zip \
  && rm keyswitch-kicad-library.zip \
  && mv footprints ../footprints/com_github_perigoso_keyswitch-kicad-library \
  && cd .. && rm -rf tmp

# Install kbplacer Python package (still needed for subprocess calls)
RUN pip3 install --upgrade pip \
  && pip3 install "git+https://github.com/adamws/kicad-kbplacer@develop#egg=kbplacer[schematic]"

# Copy Go binary from builder
COPY --from=builder --chown=kicad /build/kicad-worker /kicad/

# Set binary as executable
RUN chmod +x /kicad/kicad-worker

# Run worker
CMD ["/kicad/kicad-worker"]
