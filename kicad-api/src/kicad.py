import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from pathvalidate import sanitize_filename, sanitize_filepath

__all__ = ["new_pcb"]

SVG_TEMPLATE_FRONT = "F.Cu,F.SilkS,Edge.Cuts"
SVG_TEMPLATE_BACK = "B.Cu,B.SilkS,Edge.Cuts"

SWITCHES_LIBRARY_PATH = f"{Path.home()}/.local/share/kicad/9.0/3rdparty/footprints/com_github_perigoso_keyswitch-kicad-library/"


def run_kbplacer(
    pcb_path: Path,
    layout: Path,
    *,
    key_distance,
    route_switches_with_diodes,
    route_rows_and_columns,
    switch_footprint,
    diode_footprint,
    log_path,
):
    # fmt: off
    cmd = [
        "python3", "-m", "kbplacer",
        "--pcb-file", pcb_path,
        "--create-sch-file",
        "--create-pcb-file",
        "--switch-footprint", switch_footprint,
        "--diode-footprint", diode_footprint,
        "--layout", layout,
        "--log-level", "INFO",
        "--key-distance", key_distance,
    ]
    # fmt: on
    if route_switches_with_diodes:
        cmd.append("--route-switches-with-diodes")
    if route_rows_and_columns:
        cmd.append("--route-rows-and-columns")
    with open(log_path, "w") as f:
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def run_kicad_svg(pcb_file, layers, output_file):
    # fmt: off
    cmd = [
        "kicad-cli", "pcb", "export", "svg",
        "--layers", layers,
        "--exclude-drawing-sheet",
        "--fit-page-to-board",
        "--mode-single",
        "-o", output_file,
        pcb_file
    ]
    # fmt: on
    subprocess.run(cmd, check=True)


def generate_render(pcb_path: Path, log_path: Path):
    run_kicad_svg(pcb_path, SVG_TEMPLATE_FRONT, log_path.parent / "front.svg")
    run_kicad_svg(pcb_path, SVG_TEMPLATE_BACK, log_path.parent / "back.svg")


def generate_schematic_image(schematic_path: Path, log_path: Path):
    # fmt: off
    cmd = [
        "kicad-cli", "sch", "export", "svg",
        "--exclude-drawing-sheet",
        "--output",
        schematic_path.parent,
        schematic_path,
    ]
    # fmt: on
    result = subprocess.run(cmd, text=True, check=False)
    name = schematic_path.stem
    expected_result = schematic_path.parent / f"{name}.svg"
    if not expected_result.exists():
        msg = "Failed to generate schematic image"
        if result.stderr:
            msg += ": " + result.stderr
        raise RuntimeError(msg)
    shutil.copy(expected_result, log_path.parent / "schematic.svg")


def create_work_dir(task_id: str) -> Path:
    workdir = tempfile.mkdtemp(prefix=task_id)
    return Path(workdir).absolute()


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


def new_pcb(task_id, task_request) -> Path:
    layout = task_request["layout"]
    settings = task_request["settings"]

    switch_footprint= SWITCHES_LIBRARY_PATH + settings["switchFootprint"]
    diode_footprint= "/usr/share/kicad/footprints/" + settings["diodeFootprint"]
    route_switches_with_diodes = settings["routing"] in ["Switch-Diode only", "Full"]
    route_rows_and_columns = settings["routing"] == "Full"
    key_distance = settings["keyDistance"]

    work_dir = create_work_dir(task_id)

    project_name = get_project_name(layout["meta"]["name"])
    project_full_path = create_kicad_work_dir(work_dir, project_name)

    log_dir = create_log_dir(work_dir)
    log_path = log_dir / "build.log"

    sch_file = project_full_path / (project_name + ".kicad_sch")
    pcb_file = project_full_path / (project_name + ".kicad_pcb")

    layout_file = project_full_path / (project_name + ".json")
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    run_kbplacer(
        pcb_file,
        layout_file,
        key_distance=key_distance,
        route_switches_with_diodes=route_switches_with_diodes,
        route_rows_and_columns=route_rows_and_columns,
        switch_footprint=switch_footprint,
        diode_footprint=diode_footprint,
        log_path=log_path,
    )

    generate_schematic_image(sch_file, log_path)
    generate_render(pcb_file, log_path)

    return work_dir
