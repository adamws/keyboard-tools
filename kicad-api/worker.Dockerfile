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

ADD --chown=user:user kicad-project-template kicad-project-template

RUN curl -LJO https://github.com/ai03-2725/MX_Alps_Hybrid/archive/master.zip \
  && unzip MX_Alps_Hybrid-master.zip \
  && mkdir -p kicad-project-template/libs \
  && mv MX_Alps_Hybrid-master kicad-project-template/libs/MX_Alps_Hybrid \
  && rm -rf MX_Alps_Hybrid-master.zip

ENV KICAD_SYMBOL_DIR=/usr/share/kicad/library
ENV KISYSMOD=/usr/share/kicad/modules

RUN curl -O https://raw.githubusercontent.com/adamws/kicad-kbplacer/master/keyautoplace.py

