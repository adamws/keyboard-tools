# Introduction

KiCad project generator aims to simplify and speed up design process for
mechanical keyboard's PCBs. This tool provides template project based
on layout generated by [keyboard-layout-editor](http://www.keyboard-layout-editor.com).

Contrary to other similar projects, it uses [SKiDL](https://xess.com/skidl) for
generating netlist and KiCad's python API for PCB manipulation. As a consequence
it should provide better maintainability and be more robust and feature reach.
