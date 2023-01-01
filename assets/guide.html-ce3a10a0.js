import{_ as n,M as s,p as i,q as r,R as e,t,N as a,a1 as l}from"./framework-96b046e1.js";const c="/keyboard-tools/assets/layout60-0768e26d.png",d="/keyboard-tools/assets/frontend-311bf2a3.png",p="/keyboard-tools/assets/kicad-project-423d157c.png",u="/keyboard-tools/assets/pcb-7c6632e7.png",m="/keyboard-tools/assets/drc-result-10bf57bb.png",h="/keyboard-tools/assets/drc-fix-34b1a0bc.png",g="/keyboard-tools/assets/prompt-bfc9d496.png",_="/keyboard-tools/assets/uc-circuit-4934f18a.png",b="/keyboard-tools/assets/load-netlist-9cc5a90a.png",f={},y=e("h1",{id:"guide",tabindex:"-1"},[e("a",{class:"header-anchor",href:"#guide","aria-hidden":"true"},"#"),t(" Guide")],-1),k=e("p",null,"KiCad project generator does not generate PCBs ready for fabrication. User needs to design microcontroller circuit and route everything together.",-1),w=e("p",null,[t("In this guide I'm using "),e("code",null,"Default 60%"),t(" preset from "),e("a",{href:"www.keyboard-layout-editor.com"},"keyboard-layout-editor"),t(".")],-1),v=e("p",null,[e("img",{src:c,alt:"pcb"})],-1),x=e("p",null,"Recommended workflow contains following steps:",-1),C=e("li",null,[e("p",null,[t("Download json layout of your design (attention: this is not data from "),e("strong",null,"Raw data"),t(" tab. Use "),e("strong",null,"Download JSON"),t(" button).")])],-1),I={href:"http://keyboard-tools.xyz/",target:"_blank",rel:"noopener noreferrer"},j=e("p",null,[t("In this example I decided to use "),e("em",null,"Cherry MX"),t(" footprints and I enabled routing. Because I did not used key annotations (see "),e("a",{href:"features#matrix-position-assignment"},"this"),t(") I used "),e("em",null,"Automatic"),t(" matrix option.")],-1),B=e("p",null,[t("If everything succeed, after few seconds, PCB preview and "),e("strong",null,"Download project"),t(" button (4) should appear:")],-1),D=e("p",null,[e("img",{src:d,alt:"frontend"})],-1),P=l('<li><p>Download and unzip project. Open project located in <code>keyboard</code> directory. It should contain following structure:</p><p><img src="'+p+'" alt="kicad-project"></p><div class="custom-container tip"><p class="custom-container-title">TIP</p><p>Generated project has entire selected switch library bundled in. This makes footprint replacement easy.</p></div><p><code>keyboard.kicad_pcb</code> file should have switches and diodes placed according to provided layout like this:</p><p><img src="'+u+'" alt="pcb"></p><ul><li><p>Run DRC check. In this example, there is one invalid track.</p><p><img src="'+m+'" alt="pcb"></p><p>In order to fix it, simple remove faulty track segment and route it manually, for example:</p><p><img src="'+h+'" alt="pcb"></p><p>Also check if DRC report any unconnected items. For some layouts, current router implementation does not attempt to connect items (mainly diodes with different <code>Y</code> coordinate).</p><div class="custom-container tip"><p class="custom-container-title">TIP</p><p>Always run DRC check on imported projects. Implemented router does not guarantee that rules are met, for details see <a href="features#routing">this</a>.</p></div></li></ul></li><li><p>From this point onward, PCB needs to be finished by user.</p><ul><li><p>Open <code>Schematic Layout Editor</code>, because schematic is not generated there will be following prompt:</p><p><img src="'+g+'" alt="prompt"></p><p>Select <strong>yes</strong>.</p></li><li><p>Design microcontroller circuit, for example:</p><p><img src="'+_+'" alt="uc-circuit"></p><p>For connecting key matix rows/collumns use <code>Global Labels</code> with following name convention: <code>ROW{number}</code>/<code>COL{number}</code></p><div class="custom-container tip"><p class="custom-container-title">TIP</p><p>Generating MCU circuitry is planned in future releases.</p></div></li><li><p>Generate netlist (<code>Tools-&gt;Generate Netlist File</code>). Remember to rename it, otherwise key matrix netlist will be overwritten (by default, KiCad names netlist same as project).</p></li><li><p>Open <code>keyboard.kicad_pcb</code> and load microcontroller netlist.</p><p><img src="'+b+'" alt="load-netlist"></p><p>Click <strong>Upadate PCB</strong> and <strong>Close</strong>. New components will appear on PCB.</p></li><li><p>Finish placement and routing.</p></li></ul></li>',2);function R(G,N){const o=s("ExternalLinkIcon");return i(),r("div",null,[y,k,w,v,x,e("ul",null,[C,e("li",null,[e("p",null,[t("Go to "),e("a",I,[t("keyboard-tools's"),a(o)]),t(" KiCad Project Generator tab (1), choose project options (2) and upload keyboard layout (3).")]),j,B,D]),P])])}const T=n(f,[["render",R],["__file","guide.html.vue"]]);export{T as default};
