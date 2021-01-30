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

RUN curl -LJO https://github.com/ai03-2725/MX_Alps_Hybrid/archive/master.zip \
  && unzip MX_Alps_Hybrid-master.zip \
  && mkdir switch-libs \
  && mv MX_Alps_Hybrid-master switch-libs/MX_Alps_Hybrid \
  && rm -rf MX_Alps_Hybrid-master.zip \
  && curl -LJO https://github.com/perigoso/Switch_Keyboard/archive/main.zip \
  && unzip Switch_Keyboard-main.zip \
  && mv Switch_Keyboard-main switch-libs/Switch_Keyboard \
  && rm -rf Switch_Keyboard-main.zip

ENV KICAD_SYMBOL_DIR=/usr/share/kicad/library
ENV KISYSMOD=/usr/share/kicad/modules

RUN curl -O https://raw.githubusercontent.com/adamws/kicad-kbplacer/master/keyautoplace.py

