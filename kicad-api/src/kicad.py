import glob
import json
import logging
import os
import re
import shutil
from pathlib import Path

import pcbnew
from kbplacer.defaults import ZERO_POSITION
from kbplacer.edge_generator import build_board_outline
from kbplacer.element_position import ElementInfo, ElementPosition, Point, PositionOption, Side
from kbplacer.key_placer import KeyPlacer
from kbplacer.template_copier import copy_from_template_to_board
from kinet2pcb import kinet2pcb
from kle2netlist.skidl import build_circuit, generate_netlist
from pcbdraw.plot import PcbPlotter
from skidl.logger import logger as skidl_logger
from skidl.logger import erc_logger as skidl_erc_logger

__all__ = ["new_pcb"]


def run_element_placement_and_routing(board: pcbnew.BOARD, layout, settings):
    DIODE_POSITION = ElementPosition(Point(5.08, 4), 90.0, Side.BACK)
    switch = ElementInfo("SW{}", PositionOption.DEFAULT, ZERO_POSITION, "")
    diode = ElementInfo("D{}", PositionOption.CUSTOM, DIODE_POSITION, "")
    route_switches_with_diodes = settings["routing"] in ["Switch-Diode only", "Full"]
    route_rows_and_columns = settings["routing"] == "Full"
    additional_elements = [
        ElementInfo("ST{}", PositionOption.CUSTOM, ZERO_POSITION, "")
    ]

    placer = KeyPlacer(board, (19.05, 19.05))
    placer.run(
        layout,
        switch,
        diode,
        route_switches_with_diodes,
        route_rows_and_columns,
        additional_elements,
    )


def generate_render(pcb_path: Path):
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

    for f in glob.glob(f"{project_full_path}/render*"):
        os.remove(f)


def configure_loggers(log_path):
    log_path = f"{log_path}/build.log"
    ch = logging.FileHandler(log_path, mode="w")
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("[%(asctime)s %(filename)s:%(lineno)d]: %(message)s"))

    dependencies_loggers = [
        logging.getLogger("kbplacer"),
        logging.getLogger("kinet2pcb"),
        skidl_logger,
        skidl_erc_logger
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


def new_pcb(task_id, task_request, update_state_callback):
    update_state_callback(0)

    layout = task_request["layout"]
    settings = task_request["settings"]

    project_name = layout["meta"]["name"]
    project_name = "keyboard" if project_name == "" else project_name
    project_full_path = str(Path(task_id).joinpath(project_name).absolute())
    Path(project_full_path).mkdir(parents=True, exist_ok=True)

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    configure_loggers(log_path)

    update_state_callback(10)
    sanitize_keys(layout["keys"])

    pcb_file = f"{project_full_path}/{project_name}.kicad_pcb"
    netlist_file = f"{project_full_path}/{project_name}.net"
    layout_file = f"{project_full_path}/{project_name}_layout.json"
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
    generate_netlist(netlist_file)

    update_state_callback(30)
    libraries = ["/usr/share/kicad/footprints"]
    footprints = Path(f"{Path.home()}/.local/share/kicad/7.0/3rdparty/footprints")
    for path in footprints.iterdir():
        if path.is_dir():
            libraries.append(str(path))
    kinet2pcb(netlist_file, pcb_file, libraries)

    update_state_callback(40)
    board = pcbnew.LoadBoard(pcb_file)

    # do template first because otherwise we sometimes get segmentation
    # fault on pcbnew.SaveBoard when routing enabled, most likely there is a problem
    # with kbplacer which should be solved, for now this workaround is ok...
    if settings["controllerCircuit"] == "ATmega32U4":
        template_path = str(
            Path.home().joinpath("templates/atmega32u4-au-v1.kicad_pcb")
        )
        route_template = settings["routing"] == "Full"
        copy_from_template_to_board(board, template_path, route_template)


    update_state_callback(50)
    run_element_placement_and_routing(board, layout_file, settings)

    update_state_callback(60)
    build_board_outline(board, 5, "SW{}")

    pcbnew.Refresh()
    pcbnew.SaveBoard(pcb_file, board)

    update_state_callback(70)
    generate_render(Path(pcb_file))

    update_state_callback(80)
    shutil.make_archive(task_id, "zip", task_id)

    return log_path


