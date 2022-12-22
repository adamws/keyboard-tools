FROM admwscki/kicad-kbplacer:latest

ENV PATH="/kicad/.local/bin:${PATH}"

RUN mkdir switch-libs \
  && cd switch-libs \
  && git clone --depth 1 https://github.com/ai03-2725/MX_Alps_Hybrid \
  && git clone https://github.com/perigoso/keyswitch-kicad-library \
  && cd keyswitch-kicad-library && git checkout e56f74e93c850e60e04023563835b5fe031fd638

RUN mkdir templates \
  && cd templates \
  && wget https://raw.githubusercontent.com/adamws/kle2netlist/master/kicad-templates/atmega32u4-au-v1/atmega32u4-au-v1.kicad_pcb

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY src /kicad/src

