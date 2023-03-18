FROM admwscki/kicad-kbplacer:0.3.f3eba0067482cda7a19275c84b3481d89b917024

ENV PATH="/kicad/.local/bin:${PATH}"

RUN mkdir switch-libs \
  && cd switch-libs \
  && mkdir keyswitch-kicad-library && cd keyswitch-kicad-library \
  && wget https://github.com/perigoso/keyswitch-kicad-library/releases/download/v2.2/keyswitch-kicad-library.zip \
  && unzip keyswitch-kicad-library.zip \
  && rm keyswitch-kicad-library.zip

RUN mkdir templates \
  && cd templates \
  && wget https://raw.githubusercontent.com/adamws/kle2netlist/v0.2/kicad-templates/atmega32u4-au-v1/atmega32u4-au-v1.kicad_pcb

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY src /kicad/src

