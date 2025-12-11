FROM admwscki/kicad-kbplacer-primary:9.0.6-noble

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

# simulate installation with KiCad's PCM (we care only about footprints):
RUN cd /kicad/.local/share/kicad/9.0/3rdparty \
  && mkdir -p footprints \
  && mkdir tmp && cd tmp \
  && wget https://github.com/kiswitch/keyswitch-kicad-library/releases/download/v2.4/keyswitch-kicad-library.zip \
  && echo "b38d56323acb91ad660567340ca938c5b4a83a27eea52308ef14aa7857b0071b keyswitch-kicad-library.zip" | sha256sum -c \
  && unzip keyswitch-kicad-library.zip \
  && rm keyswitch-kicad-library.zip \
  && mv footprints ../footprints/com_github_perigoso_keyswitch-kicad-library \
  && cd .. && rm -rf tmp

COPY --chown=kicad requirements.txt .
RUN pip3 install --upgrade pip \
  && pip3 install -r requirements.txt

RUN pip3 install git+https://github.com/adamws/kicad-svg-extras.git

COPY --chown=kicad src /kicad/src
