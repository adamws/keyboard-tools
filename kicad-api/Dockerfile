FROM admwscki/kicad-kbplacer:latest

ENV PATH="/workspace/.local/bin:${PATH}"

RUN mkdir switch-libs \
  && cd switch-libs \
  && git clone --depth 1 https://github.com/ai03-2725/MX_Alps_Hybrid \
  && git clone --depth 1 https://github.com/perigoso/keyswitch-kicad-library

RUN mkdir templates \
  && cd templates \
  && wget https://raw.githubusercontent.com/adamws/kle2netlist/master/kicad-templates/atmega32u4-au-v1/atmega32u4-au-v1.kicad_pcb

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY src /workspace/src

