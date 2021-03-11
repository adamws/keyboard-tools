import datetime
import json
import os
import re
import shutil
import subprocess
import pcbnew

from pathlib import Path

from jinja2 import Template


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
    if switch_library == "perigoso/keyswitch-kicad-library":
        prefix = "${KIPRJMOD}/libs/keyswitch-kicad-library/modules"
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
        prefix = "${KIPRJMOD}/libs/MX_Alps_Hybrid"
        fp_lib_table = tm.render(
            fp_libs=[
                f'(lib (name MX_Only)(type KiCad)(uri {prefix}/MX_Only.pretty)(options "")(descr ""))'
                f'(lib (name Alps_Only)(type KiCad)(uri {prefix}/Alps_Only.pretty)(options "")(descr ""))'
                f'(lib (name MX_Alps_Hybrid)(type KiCad)(uri {prefix}/MX_Alps_Hybrid.pretty)(options "")(descr ""))'
            ]
        )
        shutil.copytree(
            "switch-libs/MX_Alps_Hybrid", f"{project_full_path}/libs/MX_Alps_Hybrid"
        )

    with open(f"{project_full_path}/fp-lib-table", "w") as f:
        f.write(fp_lib_table)

    with open(f"{project_full_path}/{project_name}.kicad_pcb", "w") as f:
        f.write('(kicad_pcb (version 4) (host kicad "dummy file") )')

    with open(f"{project_full_path}/{project_name}.pro", "w") as f:
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        f.write(f"update={timestamp}\n")
        f.write("version=1\n")
        f.write("last_client=kicad\n")
        f.write("[general]\n")
        f.write("version=1\n")
        f.write("RootSch=\n")
        f.write("BoardNm=\n")
        f.write("[pcbnew]\n")
        f.write("version=1\n")
        f.write("LastNetListRead=\n")
        f.write("UseCmpFile=1\n")
        f.write("[cvpcb]\n")
        f.write("version=1\n")
        f.write("NetIExt=net\n")
        f.write("[eeschema]\n")
        f.write("version=1\n")
        f.write("LibDir=\n")
        f.write("[keyboard-tools]\n")
        f.write("url=keyboard-tools.xyz\n")


def generate_netlist(
    project_full_path, layout_file, netlist_path, switch_library, switch_footprint, controller_circuit
):
    project_libs = "/usr/share/kicad/library"

    kle2netlist_log = open(f"{project_full_path}/../logs/kle2netlist.log", "w")

    args = [
            "kle2netlist",
            "--layout",
            layout_file,
            "--output",
            netlist_path,
            "--switch-library",
            switch_library,
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
        raise Exception("Generate netlist failed")


def generate_pcb_file(project_full_path, project_name):
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path

    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    kicad_pcb_log = open(f"{project_full_path}/../logs/kinet2pcb.log", "w")

    p = subprocess.Popen(
        ["kinet2pcb", "-w", "-nb", "-i", f"{project_name}.net"],
        cwd=project_full_path,
        env=env,
        stdout=kicad_pcb_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        raise Exception("Generate .kicad_pcb from netlist failed")


def run_element_placement(project_full_path, project_name, layout_file, settings):
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path

    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    keyautoplace_log = open(f"{project_full_path}/../logs/keyautoplace.log", "w")

    keyautoplace_args = [
        "python3",
        "keyautoplace.py",
        "-l",
        layout_file,
        "-b",
        pcb_path,
    ]
    if settings["routing"] == "Full":
        keyautoplace_args.append("--route")
    if settings["controllerCircuit"] == "ATmega32U4":
        keyautoplace_args.append("-t")
        keyautoplace_args.append("/workspace/templates/atmega32u4-au-v1.kicad_pcb")

    p = subprocess.Popen(
        keyautoplace_args,
        env=env,
        stdout=keyautoplace_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        raise Exception("Switch placement failed")


def add_edge_cuts(project_full_path, project_name):
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"
    try:
        board = pcbnew.LoadBoard(pcb_path)
        positions = [
            module.GetPosition()
            for module in board.GetModules()
            if re.match(r"^SW\d+$", module.GetReference())
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
            segment = pcbnew.DRAWSEGMENT(board)
            segment.SetLayer(pcbnew.Edge_Cuts)
            segment.SetStart(start)
            segment.SetEnd(end)
            board.Add(segment)

        pcbnew.Refresh()
        pcbnew.SaveBoard(pcb_path, board)
    except Exception as err:
        raise Exception("Adding egde cuts failed") from err


def generate_render(project_full_path, project_name):
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path

    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"

    # render is performed on copy of pcb from which all parts except
    # switches and diodes were removed. This is due to microcontroller circuit
    # which may be present but its placement is outside board outline
    pcb_for_render = f"{project_full_path}/{project_name}_render.kicad_pcb"

    shutil.copyfile(pcb_path, pcb_for_render)

    try:
        board = pcbnew.LoadBoard(pcb_for_render)
        module = board.GetModules().GetFirst()
        while module:
            current_module = module
            reference = current_module.GetReference()
            module = current_module.Next()
            if not re.match(r"^(SW|D)\d+$", reference):
                board.Delete(current_module)

        # include only collumn/row tracks in render in case
        # there are microcontroller circuit tracks present
        track = board.GetTracks().GetFirst()
        while track:
            current_track = track
            name = current_track.GetNetname()
            track = track.Next()
            if not re.match(r"^(ROW|COL|N\$)\d+$", name):
                board.Delete(current_track)

        pcbnew.Refresh()
        pcbnew.SaveBoard(pcb_for_render, board)
    except Exception as err:
        raise Exception("Removing modules before render generation failed") from err

    pcbdraw_log = open(f"{project_full_path}/../logs/pcbdraw.log", "w")
    p = subprocess.Popen(
        [
            "pcbdraw",
            "--filter",
            '""',
            pcb_for_render,
            f"{project_full_path}/../logs/front.svg",
        ],
        env=env,
        stdout=pcbdraw_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        raise Exception("Preview render failed")

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
    netlist_path = f"{project_full_path}/{project_name}.net"

    update_state_callback(10)
    prepare_project(project_full_path, project_name, switch_library)

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    update_state_callback(20)
    generate_netlist(
        project_full_path, layout_file, netlist_path, switch_library, switch_footprint, controller_circuit
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
