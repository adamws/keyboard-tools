import datetime
import json
import os
import re
import shutil
import subprocess
import traceback

from pathlib import Path

from celery import Celery, states
from celery.exceptions import Ignore
from jinja2 import Template
from minio import Minio
from minio.commonconfig import ENABLED
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379"
)

minio_access_key = os.environ.get("MINIO_ACCESS_KEY", "minio_dev")
minio_secret_key = os.environ.get("MINIO_SECRET_KEY", "minio_dev_secret")


def __update_percentage(percentage):
    generate_kicad_project.update_state(
        state="PROGRESS", meta={"percentage": percentage}
    )


def __prepare_project(project_full_path, project_name, switch_library):
    __update_percentage(10)

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
                '(lib (name MX_Only)(type KiCad)(uri {prefix}/MX_Only.pretty)(options "")(descr ""))'
                '(lib (name Alps_Only)(type KiCad)(uri {prefix}/Alps_Only.pretty)(options "")(descr ""))'
                '(lib (name MX_Alps_Hybrid)(type KiCad)(uri {prefix}/MX_Alps_Hybrid.pretty)(options "")(descr ""))'
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


def __upload_to_storage(task_id, log_path):
    client = Minio(
        "minio:9000",
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=False,
    )

    bucket_name = "kicad-projects"
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        config = LifecycleConfig(
            [
                Rule(
                    ENABLED,
                    rule_id="expire",
                    expiration=Expiration(days=1),
                ),
            ],
        )
        client.set_bucket_lifecycle("kicad-projects", config)

    client.fput_object(
        bucket_name, f"{task_id}/{task_id}.zip", f"/workspace/{task_id}.zip"
    )
    client.fput_object(bucket_name, f"{task_id}/front.svg", f"{log_path}/front.svg")


def __generate_kicad_project(task_id, task_request):
    import pcbnew

    __update_percentage(0)

    layout = task_request["layout"]
    settings = task_request["settings"]

    switch_library = settings["switchLibrary"]
    switch_footprint = settings["switchFootprint"]

    project_name = layout["meta"]["name"]
    project_name = "keyboard" if project_name == "" else project_name
    project_full_path = str(Path(task_id).joinpath(project_name).absolute())
    netlist_path = f"{project_full_path}/{project_name}.net"

    # 1. prepare project
    __prepare_project(project_full_path, project_name, switch_library)

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)

    # 2. generate netlist
    __update_percentage(20)
    kle2netlist_log = open("kle2netlist.log", "w")
    project_libs = "/usr/share/kicad/library"
    p = subprocess.Popen(
        [
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
        ],
        stdout=kle2netlist_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        raise Exception("Generate netlist failed")

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
    if p.returncode != 0:
        raise Exception("Generate .kicad_pcb from netlist failed")

    # 4. arrange elements on pcb
    __update_percentage(40)
    keyautoplace_log = open("keyautoplace.log", "w")
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

    p = subprocess.Popen(
        keyautoplace_args,
        env=env,
        stdout=keyautoplace_log,
        stderr=subprocess.STDOUT,
    )
    p.communicate()
    if p.returncode != 0:
        raise Exception("Switch placement failed")

    # 5. add edge cuts
    __update_percentage(50)
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
    if p.returncode != 0:
        raise Exception("Preview render failed")

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
    __upload_to_storage(task_id, log_path)


@celery.task(name="generate_kicad_project")
def generate_kicad_project(task_request):
    task_id = generate_kicad_project.request.id
    try:
        __generate_kicad_project(task_id, task_request)
    except Exception as err:
        generate_kicad_project.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(err).__name__,
                "exc_message": traceback.format_exc(limit=1),
            },
        )
        raise Ignore() from err
    finally:
        shutil.rmtree(task_id, ignore_errors=True)
        zipfile = f"{task_id}.zip"
        if os.path.isfile(zipfile):
            os.remove(zipfile)

    return {"percentage": 100}
