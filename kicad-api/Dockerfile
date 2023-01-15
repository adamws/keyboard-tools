FROM admwscki/kicad-kbplacer:0.1.48a297d8365797c2a3ed3cebcf7d7548658a7779

ENV PATH="/kicad/.local/bin:${PATH}"

RUN mkdir switch-libs \
  && cd switch-libs \
  && mkdir keyswitch-kicad-library && cd keyswitch-kicad-library \
  && wget https://github.com/perigoso/keyswitch-kicad-library/releases/download/v2.2/keyswitch-kicad-library.zip \
  && unzip keyswitch-kicad-library.zip \
  && rm keyswitch-kicad-library.zip

RUN mkdir templates \
  && cd templates \
  && wget https://raw.githubusercontent.com/adamws/kle2netlist/master/kicad-templates/atmega32u4-au-v1/atmega32u4-au-v1.kicad_pcb

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY src /kicad/src

