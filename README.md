<div align="center">

<img src="https://raw.githubusercontent.com/adamws/keyboard-tools/master/webapp/src/assets/logo.png" width="300">

# Keyboard tools

[![Website](https://img.shields.io/website?down_message=offline&up_message=up&url=http%3A%2F%2Fkeyboard-tools.xyz)](http://keyboard-tools.xyz)
[![CircleCI](https://circleci.com/gh/adamws/keyboard-tools.svg?style=shield)](https://circleci.com/gh/adamws/keyboard-tools/tree/master)
[![GitHub](https://img.shields.io/github/license/adamws/keyboard-tools)](https://github.com/adamws/keyboard-tools/blob/master/LICENSE)

</div>

## KiCad project generator

- web interface available at [keyboard-tools.xyz](http://keyboard-tools.xyz)
- two switch libraries to choose from: [MX_Alps_Hybrid](https://github.com/ai03-2725/MX_Alps_Hybrid)
  and [keyswitch-kicad-library](https://github.com/perigoso/keyswitch-kicad-library)
- three available switch footprints: Cherry MX, Alps and Cherry MX/Alps hybrid
- key rotations thanks to patched [kle-serial](https://github.com/ijprest/kle-serial)
- supports basic pre-routing

Detailed documentation available here: [keyboard-tools/kicad-project-generator](https://adamws.github.io/keyboard-tools/kicad-project-generator)

## KLE converter

- use [kle-serial](https://github.com/ijprest/kle-serial) via web interface at [keyboard-tools.xyz/kle-converter](http://keyboard-tools.xyz/kle-converter)
- includes [patch](https://github.com/ijprest/kle-serial/pull/1) which fix
  rotated key issue

## Development

For development guide see [this](https://adamws.github.io/keyboard-tools/kicad-project-generator/development).

## Credits

- keyboard layout file serialized by [kle-serial](https://github.com/ijprest/kle-serial)
- netlist generated with [skidl](https://github.com/xesscorp/skidl) based [kle2netlist](https://github.com/adamws/kle2netlist)
- switch footprints by [MX_Alps_Hybrid](https://github.com/ai03-2725/MX_Alps_Hybrid)
  and [keyswitch-kicad-library](https://github.com/perigoso/keyswitch-kicad-library)
- key placement with [kicad-kbplacer](https://github.com/adamws/kicad-kbplacer)
- pcb preview generated with [pcbdraw](https://github.com/yaqwsx/PcbDraw)
- project structure generated with [goxygen](https://github.com/Shpota/goxygen)
