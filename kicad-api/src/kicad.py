import glob
import json
import logging
import os
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
from kbplacer.template_copier import copy_from_template_to_board
from kinet2pcb import kinet2pcb
from kle2netlist.skidl import build_circuit, generate_netlist
from pathvalidate import sanitize_filename, sanitize_filepath
from skidl.logger import logger as skidl_logger
from skidl.logger import erc_logger as skidl_erc_logger

__all__ = ["new_pcb"]


def run_controller_circuit_template_copy(board: pcbnew.BOARD, settings):
    if settings["controllerCircuit"] == "ATmega32U4":
        template_path = str(
            Path.home().joinpath("templates/atmega32u4-au-v1.kicad_pcb")
        )
        route_template = settings["routing"] == "Full"
        copy_from_template_to_board(board, template_path, route_template)


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


def generate_render(pcb_path: Path, log_path: Path):
    # render is performed on copy of pcb from which all parts outside board edge
    # were removed. This is due to microcontroller circuit which may be present
    # but its placement is outside board outline
    project_full_path = Path(pcb_path).parent
    pcb_for_render = pcb_path.with_stem("render")

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

    pcbdraw_log = open(log_path, "a")

    # running pcbdraw in subprocess because importing it directly
    # interferes with pcbnew due to buggy pcbnewTransition which attempts
    # to provide kicad version independent interface to pcbnew but instead makes some
    # pcbnew functionality broken (in case of this application, kbplacer routing
    # would be wrong)
    def _pcbdraw(args):
        subprocess.run(
            ["pcbdraw", "plot"] + args,
            stdout=pcbdraw_log,
            stderr=subprocess.STDOUT,
        )

    _pcbdraw([pcb_for_render, log_path.parent / "front.svg"])
    _pcbdraw(
        ["--side", "back", "--mirror", pcb_for_render, log_path.parent / "back.svg"]
    )

    pcbdraw_log.close()

    for f in glob.glob("render*", root_dir=project_full_path):
        os.remove(project_full_path / f)


def configure_loggers(log_path: Path):
    ch = logging.FileHandler(log_path, mode="w")
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter("[%(asctime)s %(filename)s:%(lineno)d]: %(message)s")
    )

    dependencies_loggers = [
        logging.getLogger("kbplacer"),
        logging.getLogger("kinet2pcb"),
        skidl_logger,
        skidl_erc_logger,
    ]
    for logger in dependencies_loggers:
        for handler in logger.handlers:
            try:
                logger.removeHandler(handler)
            except:
                # removing handler from skidl logger might trigger removing of
                # a file which does not exist. Ignore all issues with logger handlers.
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

    pcb_file = project_full_path / (project_name + ".kicad_pcb")
    netlist_file = project_full_path / (project_name + ".net")
    layout_file = project_full_path / (project_name + ".json")
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    update_state_callback(20)
    build_circuit(
        layout,
        switch_footprint=settings["switchFootprint"],
        stabilizer_footprint="Mounting_Keyboard_Stabilizer:Stabilizer_Cherry_MX_{:.2f}u",
        diode_footprint=settings["diodeFootprint"],
        additional_search_path="/usr/share/kicad/library",
        controller_circuit=settings["controllerCircuit"] == "ATmega32U4",
    )
    generate_netlist(str(netlist_file))

    update_state_callback(30)
    libraries = ["/usr/share/kicad/footprints"]
    footprints = Path(f"{Path.home()}/.local/share/kicad/7.0/3rdparty/footprints")
    for path in footprints.iterdir():
        if path.is_dir():
            libraries.append(str(path))
    kinet2pcb(str(netlist_file), pcb_file, libraries)

    board = pcbnew.LoadBoard(pcb_file)

    # do template first because otherwise we sometimes get segmentation
    # fault on pcbnew.SaveBoard when routing enabled, most likely there is a problem
    # with kbplacer which should be solved, for now this workaround is ok...
    update_state_callback(40)
    run_controller_circuit_template_copy(board, settings)

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
