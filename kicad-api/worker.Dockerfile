FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y \
      software-properties-common \
      curl \
      git \
      unzip \
      python3-pip \
      libmagickwand-dev

RUN add-apt-repository --yes ppa:kicad/kicad-5.1-releases \
  && apt-get update \
  && apt-get install -y --no-install-recommends kicad \
     kicad-footprints kicad-libraries kicad-symbols

COPY worker-requirements.txt .
RUN pip3 install -r worker-requirements.txt

RUN useradd --create-home --shell /bin/bash worker \
  && usermod -m -d /workspace worker

USER worker
WORKDIR /workspace

ARG AI03_LIB=MX_Alps_Hybrid
ARG PERIGOSO_LIB=keyswitch-kicad-library

RUN mkdir switch-libs \
  && curl -LJO https://github.com/ai03-2725/$AI03_LIB/archive/master.zip \
  && unzip $AI03_LIB-master.zip \
  && mv $AI03_LIB-master switch-libs/$AI03_LIB \
  && rm -rf $AI03_LIB-master.zip \
  && curl -LJO https://github.com/perigoso/$PERIGOSO_LIB/archive/main.zip \
  && unzip $PERIGOSO_LIB-main.zip \
  && mv $PERIGOSO_LIB-main switch-libs/$PERIGOSO_LIB \
  && rm -rf $PERIGOSO_LIB-main.zip

ENV KICAD_SYMBOL_DIR=/usr/share/kicad/library
ENV KISYSMOD=/usr/share/kicad/modules

RUN curl -O https://raw.githubusercontent.com/adamws/kicad-kbplacer/master/keyautoplace.py

