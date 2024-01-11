import{_ as e,c as t,o,U as r}from"./chunks/framework.cMtk_7u2.js";const s="/keyboard-tools/assets/layout60.KNAkY-RQ.png",a="/keyboard-tools/assets/frontend.K35-81NE.png",i="/keyboard-tools/assets/pcb.ie4TB0dY.png",n="/keyboard-tools/assets/drc-result.DE5DasAh.png",l="/keyboard-tools/assets/drc-fix._Ajzcw7m.png",c="/keyboard-tools/assets/prompt.vgot3ans.png",d="/keyboard-tools/assets/uc-circuit.DUvImBkG.png",p="/keyboard-tools/assets/load-netlist.CgdQxNlT.png",v=JSON.parse('{"title":"Guide","description":"","frontmatter":{},"headers":[],"relativePath":"guide.md","filePath":"guide.md"}'),m={name:"guide.md"},u=r('<h1 id="guide" tabindex="-1">Guide <a class="header-anchor" href="#guide" aria-label="Permalink to &quot;Guide&quot;">​</a></h1><p>KiCad project generator does not generate PCBs ready for fabrication. User needs to design microcontroller circuit and route everything together.</p><p>In this guide I&#39;m using <code>Default 60%</code> preset from <a href="http://keyboard-layout-editor.com" target="_blank" rel="noreferrer">keyboard-layout-editor</a>.</p><p><img src="'+s+'" alt="pcb"></p><p>Recommended workflow contains following steps:</p><ul><li><p>Download json layout of your design (attention: this is not data from <strong>Raw data</strong> tab. Use <strong>Download JSON</strong> button).</p></li><li><p>Go to <a href="http://keyboard-tools.xyz/" target="_blank" rel="noreferrer">keyboard-tools&#39;s</a> KiCad Project Generator tab (1), choose project options (2) and upload keyboard layout (3).</p><p>In this example I decided to use <em>Cherry MX</em> footprints and I enabled routing. Because I did not used key annotations (see <a href="./features#matrix-position-assignment">this</a>) I used <em>Automatic</em> matrix option.</p><p>If everything succeed, after few seconds, PCB preview and <strong>Download project</strong> button (4) should appear:</p><p><img src="'+a+'" alt="frontend"></p></li><li><p>Download and unzip project. There will be two directories. One for <code>logs</code> and the other for KiCad files.</p><p><code>*.kicad_pcb</code> file should have switches and diodes placed according to provided layout like this:</p><p><img src="'+i+'" alt="pcb"></p><ul><li><p>Run DRC check. In this example, there is one invalid track.</p><p><img src="'+n+'" alt="pcb"></p><p>In order to fix it, simple remove faulty track segment and route it manually, for example:</p><p><img src="'+l+'" alt="pcb"></p><p>Also check if DRC report any unconnected items. For some layouts, current router implementation does not attempt to connect items (mainly diodes with different <code>Y</code> coordinate).</p><div class="tip custom-block"><p class="custom-block-title">TIP</p><p>Newer <a href="https://github.com/adamws/kicad-kbplacer" target="_blank" rel="noreferrer">kicad-kbplacer</a> should not add tracks colliding with other elements but always run DRC check on imported projects. Implemented router does not guarantee that rules are met, for details see <a href="./features#routing">this</a>.</p></div></li></ul></li><li><p>From this point onward, PCB needs to be finished by user.</p><ul><li><p>Open <code>Schematic Layout Editor</code>, because schematic is not generated there will be following prompt:</p><p><img src="'+c+'" alt="prompt"></p><p>Select <strong>yes</strong>.</p></li><li><p>Design microcontroller circuit, for example:</p><p><img src="'+d+'" alt="uc-circuit"></p><p>For connecting key matrix rows/columns use <code>Global Labels</code> with following name convention: <code>ROW{number}</code>/<code>COL{number}</code></p><div class="tip custom-block"><p class="custom-block-title">TIP</p><p>Generating MCU circuitry is planned in future releases.</p></div></li><li><p>Generate netlist (<code>Tools-&gt;Generate Netlist File</code>). Remember to rename it, otherwise key matrix netlist will be overwritten (by default, KiCad names netlist same as project).</p></li><li><p>Open <code>*.kicad_pcb</code> and load microcontroller netlist.</p><p><img src="'+p+'" alt="load-netlist"></p><p>Click <strong>Upadate PCB</strong> and <strong>Close</strong>. New components will appear on PCB.</p></li><li><p>Finish placement and routing.</p></li></ul></li></ul>',6),g=[u];function h(b,f,_,k,y,w){return o(),t("div",null,g)}const x=e(m,[["render",h]]);export{v as __pageData,x as default};
