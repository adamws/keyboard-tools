FROM admwscki/kicad-kbplacer:0.8

ENV PATH="/kicad/.local/bin:${PATH}"

RUN mkdir switch-libs \
  && cd switch-libs \
  && mkdir keyswitch-kicad-library && cd keyswitch-kicad-library \
  && wget https://github.com/kiswitch/keyswitch-kicad-library/releases/download/v2.4/keyswitch-kicad-library.zip \
  && echo "b38d56323acb91ad660567340ca938c5b4a83a27eea52308ef14aa7857b0071b keyswitch-kicad-library.zip" | sha256sum -c \
  && unzip keyswitch-kicad-library.zip \
  && rm keyswitch-kicad-library.zip

RUN mkdir templates \
  && cd templates \
  && wget https://raw.githubusercontent.com/adamws/kle2netlist/v0.2/kicad-templates/atmega32u4-au-v1/atmega32u4-au-v1.kicad_pcb

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY src /kicad/src

