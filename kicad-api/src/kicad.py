import datetime
import json
import os
import re
import shutil
import subprocess
import pcbnew

from jinja2 import Template
from pathlib import Path
from pcbdraw.plot import PcbPlotter


def prepare_project(project_full_path, project_name, switch_library):
    Path(project_full_path).mkdir(parents=True, exist_ok=True)

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


def generate_netlist(
    project_full_path, layout_file, project_name, switch_library, switch_footprint, controller_circuit
):
    project_libs = "/usr/share/kicad/library"

    kle2netlist_log_path = f"{project_full_path}/../logs/kle2netlist.log"
    kle2netlist_log = open(kle2netlist_log_path, "w")

    args = [
            "kle2netlist",
            "--layout",
            layout_file,
            "--output-dir",
            project_full_path,
            "--name",
            project_name,
            "--switch-library",
            #kle2netlist does not recognize new name yet
            "perigoso/keyswitch-kicad-library",
            #switch_library,
            "--switch-footprint",
            switch_footprint,
            "-l",
            project_libs,
        ]
    if controller_circuit == "ATmega32U4":
        args.append("--controller-circuit")

    p = subprocess.Popen(
        args,
        stdout=kle2netlist_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        log = ""
        with open(kle2netlist_log_path, "r") as file:
            log = file.read()
        raise Exception(f"Generate netlist failed: details: {log}")

    kle2netlist_log.close()


def generate_pcb_file(project_full_path, project_name):
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path
    env["KICAD7_FOOTPRINT_DIR"] = "/usr/share/kicad/footprints"

    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    kicad_pcb_log_path = f"{project_full_path}/../logs/kinet2pcb.log"
    kicad_pcb_log = open(kicad_pcb_log_path, "w")

    p = subprocess.Popen(
        ["kinet2pcb", "-w", "-nb", "-i", f"{project_name}.net"],
        cwd=project_full_path,
        env=env,
        stdout=kicad_pcb_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()

    if p.returncode != 0:
        log = ""
        with open(kicad_pcb_log_path, "r") as file:
            log = file.read()
        msg = f"Generate .kicad_pcb from netlist failed, details:\n{log}"
        raise Exception(msg)

    kicad_pcb_log.close()


def run_element_placement(project_full_path, project_name, layout_file, settings):
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path

    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    kbplacer_log_path = f"{project_full_path}/../logs/kbplacer.log"
    kbplacer_log = open(kbplacer_log_path, "w")

    home_directory = Path.home()
    workdir = f"{home_directory}/.local/share/kicad/7.0/3rdparty/plugins"
    package_name = "com_github_adamws_kicad-kbplacer"
    kbplacer_args = [
        "python3",
        "-m",
        package_name,
        "-l",
        layout_file,
        "-b",
        pcb_path,
    ]
    if settings["routing"] == "Full":
        kbplacer_args.append("--route-switches-with-diodes")
        kbplacer_args.append("--route-rows-and-columns")
    if settings["controllerCircuit"] == "ATmega32U4":
        kbplacer_args.append("-t")
        kbplacer_args.append(str(Path.home().joinpath("templates/atmega32u4-au-v1.kicad_pcb")))

    p = subprocess.Popen(
        kbplacer_args,
        cwd = workdir,
        env=env,
        stdout=kbplacer_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        log = ""
        with open(kbplacer_log_path, "r") as file:
            log = file.read()
        msg = f"Switch placement failed, details:\n{log}"
        raise Exception(msg)

    kbplacer_log.close()


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

    os.remove(pcb_for_render)


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

    update_state_callback(10)
    prepare_project(project_full_path, project_name, switch_library)

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    update_state_callback(20)
    generate_netlist(
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
