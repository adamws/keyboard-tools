import json
import os
import re
import shutil
import pcbnew
import logging
import glob

from jinja2 import Template
from pathlib import Path
from pcbdraw.plot import PcbPlotter
from kle2netlist.skidl import build_circuit, generate_netlist

from kbplacer.defaults import DEFAULT_DIODE_POSITION, ZERO_POSITION
from kbplacer.element_position import ElementInfo, PositionOption
from kbplacer.key_placer import KeyPlacer
from kbplacer.template_copier import TemplateCopier

from kinet2pcb import kinet2pcb


def prepare_project(project_full_path, project_name, switch_library):
    tm = Template(
        "(sym_lib_table\n{% for sym_lib in sym_libs -%}{{ sym_lib }}\n{% endfor %})"
    )
    sym_lib_table = tm.render(sym_libs=[])
    with open(f"{project_full_path}/sym-lib-table", "w") as f:
        f.write(sym_lib_table)

    tm = Template(
        "(fp_lib_table\n{% for fp_lib in fp_libs -%}{{ fp_lib }}\n{% endfor %})"
    )
    if switch_library == "kiswitch/keyswitch-kicad-library":
        prefix = "${KIPRJMOD}/libs/keyswitch-kicad-library/footprints"
        fp_lib_table = tm.render(
            fp_libs=[
                f'(lib (name Switch_Keyboard_Cherry_MX)(type KiCad)(uri {prefix}/Switch_Keyboard_Cherry_MX.pretty)(options "")(descr ""))',
                f'(lib (name Switch_Keyboard_Alps_Matias)(type KiCad)(uri {prefix}/Switch_Keyboard_Alps_Matias.pretty)(options "")(descr ""))',
                f'(lib (name Switch_Keyboard_Hybrid)(type KiCad)(uri {prefix}/Switch_Keyboard_Hybrid.pretty)(options "")(descr ""))',
                f'(lib (name Mounting_Keyboard_Stabilizer)(type KiCad)(uri {prefix}/Mounting_Keyboard_Stabilizer.pretty)(options "")(descr ""))',
            ]
        )
        shutil.copytree(
            "switch-libs/keyswitch-kicad-library",
            f"{project_full_path}/libs/keyswitch-kicad-library",
        )
    else:
        msg = "Unsupported switch library"
        raise Exception(msg)

    with open(f"{project_full_path}/fp-lib-table", "w") as f:
        f.write(fp_lib_table)

    with open(f"{project_full_path}/{project_name}.kicad_pcb", "w") as f:
        f.write('(kicad_pcb (version 4) (host kicad "dummy file") )')

    file_path = os.path.dirname(os.path.realpath(__file__))
    with open(f"{file_path}/keyboard.kicad_pro.template", "r") as f:
        template = Template(f.read())
        result = template.render(project_name = project_name)
        with open(f"{project_full_path}/{project_name}.kicad_pro", "w") as f:
            f.write(result)


def generate_netlist_from_layout(
    project_full_path, layout_file, project_name, switch_library, switch_footprint, controller_circuit
):
    project_libs = "/usr/share/kicad/library"
    with open(layout_file) as f:
        json_layout = json.loads(f.read())
        build_circuit(
            json_layout,
            switch_library=switch_library,
            switch_footprint=switch_footprint,
            diode_footprint="D_SOD-323F",
            additional_search_path=project_libs,
            controller_circuit=controller_circuit == "ATmega32U4",
        )
    generate_netlist(f"{project_full_path}/{project_name}.net")


def generate_pcb_file(project_full_path, project_name):
    input_file = f"{project_full_path}/{project_name}.net"
    output_file = os.path.splitext(input_file)[0] + ".kicad_pcb"
    kinet2pcb(input_file, output_file, [
        "/usr/share/kicad/footprints",
        f"{project_full_path}/libs/keyswitch-kicad-library/footprints",
    ])


def run_element_placement(project_full_path, project_name, layout_file, settings):
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    diode = ElementInfo("D{}", PositionOption.DEFAULT, DEFAULT_DIODE_POSITION, "")
    route_switches_with_diodes = settings["routing"] == "Full"
    route_rows_and_columns = settings["routing"] == "Full"
    additional_elements = [ElementInfo("ST{}", PositionOption.CUSTOM, ZERO_POSITION, "")]

    with open(layout_file, "r") as f:
        layout = json.load(f)

    board = pcbnew.LoadBoard(pcb_path)

    placer = KeyPlacer(board, (19.05, 19.05))
    placer.run(
        layout,
        "SW{}",
        diode,
        route_switches_with_diodes,
        route_rows_and_columns,
        additional_elements
    )

    if settings["controllerCircuit"] == "ATmega32U4":
        template_path = str(Path.home().joinpath("templates/atmega32u4-au-v1.kicad_pcb"))
        copier = TemplateCopier(board, template_path, route_rows_and_columns)
        copier.run()

    pcbnew.Refresh()
    pcbnew.SaveBoard(pcb_path, board)


def add_edge_cuts(project_full_path, project_name):
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"
    try:
        board = pcbnew.LoadBoard(pcb_path)
        positions = [
            footprint.GetPosition()
            for footprint in board.GetFootprints()
            if re.match(r"^SW\d+$", footprint.GetReference())
        ]
        xvals = [position.x for position in positions]
        yvals = [position.y for position in positions]
        xmin = min(xvals) - pcbnew.FromMM(12)
        xmax = max(xvals) + pcbnew.FromMM(12)
        ymin = min(yvals) - pcbnew.FromMM(12)
        ymax = max(yvals) + pcbnew.FromMM(12)
        corners = [
            pcbnew.wxPoint(xmin, ymin),
            pcbnew.wxPoint(xmax, ymin),
            pcbnew.wxPoint(xmax, ymax),
            pcbnew.wxPoint(xmin, ymax),
        ]
        for i in range(len(corners)):
            start = corners[i]
            end = corners[(i + 1) % len(corners)]
            segment = pcbnew.PCB_SHAPE(board)
            segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
            segment.SetLayer(pcbnew.Edge_Cuts)
            segment.SetStart(pcbnew.VECTOR2I(start))
            segment.SetEnd(pcbnew.VECTOR2I(end))
            board.Add(segment)

        pcbnew.Refresh()
        pcbnew.SaveBoard(pcb_path, board)
    except Exception as err:
        msg = "Adding egde cuts failed"
        raise Exception(msg) from err


def generate_render(project_full_path, project_name):
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    # render is performed on copy of pcb from which all parts outside board edge
    # were removed. This is due to microcontroller circuit which may be present
    # but its placement is outside board outline
    pcb_for_render = f"{project_full_path}/{project_name}_render.kicad_pcb"

    shutil.copyfile(pcb_path, pcb_for_render)

    try:
        board = pcbnew.LoadBoard(pcb_for_render)
        bbox = board.GetBoardEdgesBoundingBox()
        # assuming that there are no other elements than footprints and tracks on
        # controller circuit template (which is a case for now)
        for elem in board.GetFootprints():
            if not bbox.Contains(elem.GetPosition()):
                board.RemoveNative(elem)
        for elem in board.GetTracks():
            if not bbox.Contains(elem.GetPosition()):
                board.RemoveNative(elem)

        pcbnew.SaveBoard(pcb_for_render, board)
    except Exception as err:
        msg = "Removing footprints before render generation failed"
        raise Exception(msg) from err

    plotter = PcbPlotter(pcb_for_render)
    plotter.setup_arbitrary_data_path(".")
    plotter.setup_env_data_path()
    plotter.setup_builtin_data_path()
    plotter.setup_global_data_path()

    image = plotter.plot()
    image.write(f"{project_full_path}/../logs/front.svg")

    plotter.render_back = True
    plotter.mirror = True
    image = plotter.plot()
    image.write(f"{project_full_path}/../logs/back.svg")

    for f in glob.glob(f"{project_full_path}/*_render*"):
        os.remove(f)


def configure_loggers(log_path):
    kbplacer_log_path = f"{log_path}/kbplacer.log"
    ch = logging.FileHandler(kbplacer_log_path, mode="w")
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("[%(filename)s:%(lineno)d]: %(message)s"))

    kbplacer_logger = logging.getLogger("kbplacer")
    kbplacer_logger.setLevel(logging.DEBUG)
    kbplacer_logger.addHandler(ch)
    kbplacer_logger.propagate = False


def new_pcb(task_id, task_request, update_state_callback):
    update_state_callback(0)

    layout = task_request["layout"]
    settings = task_request["settings"]

    switch_library = settings["switchLibrary"]
    switch_footprint = settings["switchFootprint"]
    controller_circuit = settings["controllerCircuit"]

    project_name = layout["meta"]["name"]
    project_name = "keyboard" if project_name == "" else project_name
    project_full_path = str(Path(task_id).joinpath(project_name).absolute())
    Path(project_full_path).mkdir(parents=True, exist_ok=True)

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    configure_loggers(log_path)

    update_state_callback(10)
    prepare_project(project_full_path, project_name, switch_library)

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    update_state_callback(20)
    generate_netlist_from_layout(
        project_full_path, layout_file, project_name, switch_library, switch_footprint, controller_circuit
    )

    update_state_callback(30)
    generate_pcb_file(project_full_path, project_name)

    update_state_callback(40)
    run_element_placement(project_full_path, project_name, layout_file, settings)

    update_state_callback(50)
    add_edge_cuts(project_full_path, project_name)

    update_state_callback(60)
    generate_render(project_full_path, project_name)

    update_state_callback(80)
    shutil.make_archive(task_id, "zip", task_id)

    return log_path


__all__ = ["new_pcb"]
