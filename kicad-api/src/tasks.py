import errno
import importlib
import json
import os
import re
import shutil
import subprocess
import time

from celery import Celery, states
from celery.exceptions import Ignore
from minio import Minio
from minio.error import S3Error
from pathlib import Path

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379"
)

TEMPLATE_NAME = "kicad-project-template"


def __update_percentage(percentage):
    generate_kicad_project.update_state(
        state="PROGRESS", meta={"percentage": percentage}
    )


def __generate_kicad_project(task_id, layout):
    import pcbnew
    import wx

    __update_percentage(0)

    project_name = layout["meta"]["name"]
    project_name = "keyboard" if project_name == "" else project_name
    project_full_path = str(Path(task_id).joinpath(project_name).absolute())

    # 1. prepare project
    __update_percentage(10)
    shutil.copytree(TEMPLATE_NAME, project_full_path)

    for f in Path(project_full_path).rglob(f"{TEMPLATE_NAME}*"):
        f.rename(f"{f.parent}/{project_name}{f.suffix}")

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    netlist_path = f"{project_full_path}/{project_name}.net"

    # this should be read from sym_lib_table:
    project_libs = [
        f"{project_full_path}/libs/MX_Alps_Hybrid/Schematic Library",
        "/usr/share/kicad/library",
    ]

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    # 2. generate netlist
    __update_percentage(20)
    # kle2netlist(layout, netlist_path, additional_search_path=project_libs)
    kle2netlist_log = open("kle2netlist.log", "w")
    p = subprocess.Popen(
        [
            "kle2netlist",
            "--layout",
            layout_file,
            "--output",
            netlist_path,
            "-l",
            project_libs[0],
            "-l",
            project_libs[1],
        ],
        stdout=kle2netlist_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()

    # 3. create .kicad_pcb from netlist
    __update_percentage(30)
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path
    kicad_pcb_log = open("kinet2pcb.log", "w")
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"
    p = subprocess.Popen(
        ["kinet2pcb", "-w", "-nb", "-i", f"{project_name}.net"],
        cwd=project_full_path,
        env=env,
        stdout=kicad_pcb_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()

    # 4. arrange elements on pcb
    __update_percentage(40)
    keyautoplace_log = open("keyautoplace.log", "w")
    p = subprocess.Popen(
        ["python3", "keyautoplace.py", "-l", layout_file, "-b", pcb_path],
        env=env,
        stdout=keyautoplace_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()

    # 5. add edge cuts
    __update_percentage(50)
    board = pcbnew.LoadBoard(pcb_path)
    positions = [
        module.GetPosition()
        for module in board.GetModules()
        if re.match(r"^SW\d+$", module.GetReference())
    ]
    xvals = [position.x for position in positions]
    yvals = [position.y for position in positions]
    xmin = min(xvals) - pcbnew.FromMM(9)
    xmax = max(xvals) + pcbnew.FromMM(9)
    ymin = min(yvals) - pcbnew.FromMM(9)
    ymax = max(yvals) + pcbnew.FromMM(9)
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

    # 6. render
    __update_percentage(60)
    pcbdraw_log = open("pcbdraw.log", "w")
    p = subprocess.Popen(
        ["pcbdraw", "--filter", '""', pcb_path, "front.svg"],
        env=env,
        stdout=pcbdraw_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()

    # 7. move log data
    __update_percentage(70)
    shutil.move("skidl_lib_sklib.py", log_path)
    shutil.move("kle2netlist.log", log_path)
    shutil.move("kinet2pcb.log", log_path)
    shutil.move("keyautoplace.log", log_path)
    shutil.move("pcbdraw.log", log_path)
    shutil.move("front.svg", log_path)

    # 8. pack result
    __update_percentage(80)
    shutil.make_archive(task_id, "zip", task_id)

    # 9. upload to storage
    __update_percentage(90)
    client = Minio(
        "minio:9000",
        access_key="minio_dev",
        secret_key="minio_dev_secret",
        secure=False,
    )

    bucket_name = task_id
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)

    client.fput_object(bucket_name, f"{task_id}.zip", f"/home/user/{task_id}.zip")
    client.fput_object(bucket_name, "front.svg", f"{log_path}/front.svg")


@celery.task(name="generate_kicad_project")
def generate_kicad_project(layout):
    task_id = generate_kicad_project.request.id
    try:
        __generate_kicad_project(task_id, layout)
    except Exception as err:
        # TODO: add better, permament logging, also find out how to
        # send custom metadata to caller
        print(err)
        generate_kicad_project.update_state(state=states.FAILURE)
        raise Ignore()
    finally:
        shutil.rmtree(task_id, ignore_errors=True)
        zipfile = f"{task_id}.zip"
        if os.path.isfile(zipfile):
            os.remove(zipfile)

    return {"percentage": 100}
