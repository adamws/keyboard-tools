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
  && apt-get install -y kicad

COPY worker-requirements.txt .
RUN pip3 install -r worker-requirements.txt

RUN useradd -ms /bin/bash user
USER user
WORKDIR /home/user

ARG AI03_LIB=MX_Alps_Hybrid
ARG PERIGOSO_LIB=keyswitch-kicad-library

RUN mkdir switch-libs \
  && curl -LJO https://github.com/ai03-2725/$AI03_LIB/archive/master.zip \
  && unzip $AI03_LIB-master.zip \
  && mv $AI03_LIB-master switch-libs/MX_Alps_Hybrid \
  && rm -rf $AI03_LIB-master.zip \
  && curl -LJO https://github.com/perigoso/$PERIGOSO_LIB/archive/main.zip \
  && unzip $PERIGOSO_LIB-main.zip \
  && mv $PERIGOSO_LIB-main switch-libs/keyswitch-kicad-library \
  && rm -rf $PERIGOSO_LIB-main.zip

ENV KICAD_SYMBOL_DIR=/usr/share/kicad/library
ENV KISYSMOD=/usr/share/kicad/modules

RUN curl -O https://raw.githubusercontent.com/adamws/kicad-kbplacer/master/keyautoplace.py

