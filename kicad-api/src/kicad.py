import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pcbnew
from kbplacer.defaults import ZERO_POSITION
from kbplacer.edge_generator import build_board_outline
from kbplacer.element_position import (
    ElementInfo,
    ElementPosition,
    PositionOption,
    Side,
)
from kbplacer.key_placer import KeyPlacer
from kbplacer.schematic_builder import create_schematic, load_keyboard
from kinet2pcb import kinet2pcb
from pathvalidate import sanitize_filename, sanitize_filepath

__all__ = ["new_pcb"]

SVG_TEMPLATE_FRONT = "F.Cu,F.SilkS,Edge.Cuts"
SVG_TEMPLATE_BACK = "B.Cu,B.SilkS,Edge.Cuts"


def get_key_distance(settings):
    value = settings["keyDistance"]
    try:
        key_distance = tuple(map(float, value.split(" ")))
    except Exception as err:
        msg = f"Could not parse `keyDistance` value: {value}"
        raise Exception(msg) from err
    if len(key_distance) != 2:
        msg = f"Too many parts in `keyDistance` value: {value}"
        raise Exception(msg)
    return key_distance


def run_element_placement_and_routing(
    board: pcbnew.BOARD,
    layout: Path,
    *,
    key_distance,
    route_switches_with_diodes,
    route_rows_and_columns,
):
    DIODE_POSITION = ElementPosition(5.08, 4, 90.0, Side.BACK)
    switch = ElementInfo("SW{}", PositionOption.DEFAULT, ZERO_POSITION, "")
    diode = ElementInfo("D{}", PositionOption.CUSTOM, DIODE_POSITION, "")
    additional_elements = [
        ElementInfo("ST{}", PositionOption.CUSTOM, ZERO_POSITION, "")
    ]

    placer = KeyPlacer(board, key_distance)
    placer.run(
        layout,
        switch,
        diode,
        route_switches_with_diodes,
        route_rows_and_columns,
        additional_elements,
    )


def svg_mm_to_cm(svg_file):
    # Change mm to cm in width/height attributes (edit file as text)
    with open(svg_file) as f:
        content = f.read()
    content = re.sub(r'(width|height)="([0-9]*\.[0-9]*)mm"', r'\1="\2cm"', content)
    with open(svg_file, "w") as f:
        f.write(content)


def run_kicad_svg(pcb_file, layers, output_file):
    # fmt: off
    cmd = [
        "kicad-svg-extras",
        "--layers", layers,
        "-o", output_file,
        pcb_file
    ]
    # fmt: on
    subprocess.run(cmd, check=True)
    svg_mm_to_cm(output_file)


def generate_render(pcb_path: Path, log_path: Path):
    run_kicad_svg(pcb_path, SVG_TEMPLATE_FRONT, log_path.parent / "front.svg")
    run_kicad_svg(pcb_path, SVG_TEMPLATE_BACK, log_path.parent / "back.svg")


def configure_loggers(log_path: Path):
    ch = logging.FileHandler(log_path, mode="w")
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter("[%(asctime)s %(filename)s:%(lineno)d]: %(message)s")
    )

    dependencies_loggers = [
        logging.getLogger("kbplacer"),
        logging.getLogger("kinet2pcb"),
    ]
    for logger in dependencies_loggers:
        for handler in logger.handlers:
            try:
                logger.removeHandler(handler)
            except:
                # Ignore all issues with logger handlers.
                pass
        logger.setLevel(logging.DEBUG)
        logger.addHandler(ch)
        logger.propagate = False


def is_key_label_valid(label):
    if label and re.match(r"^[0-9]+,[0-9]+$", label):
        return True
    else:
        return False


def sanitize_keys(keys):
    """Make sure that labels are correct and do row-column sorting
    Some layouts, especially ergo keyboards can have weird key ordering,
    since we are requiring row/column assignments with labels,
    we can easily sort it so the annotations of added elements are more natural
    """
    for key in keys:
        labels = key["labels"]
        if not labels:
            msg = "Key labels missing"
            raise RuntimeError(msg)

        # be forgiving, remove all white spaces to fix simple mistakes:
        labels[0] = re.sub(r"\s+", "", str(labels[0]), flags=re.UNICODE)
        if not is_key_label_valid(labels[0]):
            msg = (
                f"Key label invalid: '{labels[0]}' - "
                "label needs to follow 'row,column' format, for example '1,2'"
            )
            raise RuntimeError(msg)

    def sort_key(item):
        return tuple(map(int, item["labels"][0].split(",")))

    keys.sort(key=sort_key)


def create_work_dir(task_id: str) -> Path:
    work_dir = Path(task_id)
    work_dir.mkdir()
    return work_dir.absolute()


def get_project_name(layout_name: str) -> str:
    project_name = "keyboard" if layout_name == "" else layout_name
    return sanitize_filename(project_name)


def create_kicad_work_dir(work_dir: Path, project_name: str) -> Path:
    project_dir_name = sanitize_filepath(project_name)
    project_dir = work_dir / project_dir_name
    project_dir.mkdir()
    return project_dir.absolute()


def create_log_dir(work_dir: Path) -> Path:
    log_dir = work_dir / "logs"
    log_dir.mkdir()
    return log_dir.absolute()


def generate_netlist(schematic_path: Path) -> Path:
    netlist_path = schematic_path.with_suffix(".net")

    result = subprocess.run(
        [
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--output",
            netlist_path,
            schematic_path,
        ],
        text=True,
        check=False,
    )
    if not netlist_path.exists():
        msg = "Failed to generate netlist"
        if result.stderr:
            msg += ": " + result.stderr
        raise RuntimeError(msg)

    return netlist_path


def new_pcb(task_id, task_request, update_state_callback):
    update_state_callback(0)

    layout = task_request["layout"]
    settings = task_request["settings"]

    key_distance = get_key_distance(settings)
    route_switches_with_diodes = settings["routing"] in ["Switch-Diode only", "Full"]
    route_rows_and_columns = settings["routing"] == "Full"

    work_dir = create_work_dir(task_id)

    project_name = get_project_name(layout["meta"]["name"])
    project_full_path = create_kicad_work_dir(work_dir, project_name)

    log_dir = create_log_dir(work_dir)
    log_path = log_dir / "build.log"
    configure_loggers(log_path)

    update_state_callback(10)
    sanitize_keys(layout["keys"])

    sch_file = project_full_path / (project_name + ".kicad_sch")
    pcb_file = project_full_path / (project_name + ".kicad_pcb")
    layout_file = project_full_path / (project_name + ".json")
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    update_state_callback(20)
    keyboard = load_keyboard(layout_file)
    # stabilizer footprints not supported at the moment:
    # stabilizer_footprint="Mounting_Keyboard_Stabilizer:Stabilizer_Cherry_MX_{:.2f}u",
    create_schematic(
        keyboard,
        sch_file,
        switch_footprint=settings["switchFootprint"],
        diode_footprint=settings["diodeFootprint"],
    )

    netlist_file = generate_netlist(sch_file)

    update_state_callback(30)
    libraries = ["/usr/share/kicad/footprints"]
    footprints = Path(f"{Path.home()}/.local/share/kicad/9.0/3rdparty/footprints")
    for path in footprints.iterdir():
        if path.is_dir():
            libraries.append(str(path))
    kinet2pcb(str(netlist_file), pcb_file, libraries)

    board = pcbnew.LoadBoard(pcb_file)

    update_state_callback(50)
    run_element_placement_and_routing(
        board,
        layout_file,
        key_distance=key_distance,
        route_switches_with_diodes=route_switches_with_diodes,
        route_rows_and_columns=route_rows_and_columns,
    )

    update_state_callback(60)
    build_board_outline(board, 5, "SW{}")

    pcbnew.Refresh()
    pcbnew.SaveBoard(pcb_file, board)

    update_state_callback(70)
    generate_render(pcb_file, log_path)

    update_state_callback(80)
    shutil.make_archive(task_id, "zip", task_id)

    return log_dir
