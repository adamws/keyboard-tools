import errno
import json
import os
import shutil
import subprocess
import time

from celery import Celery
from pathlib import Path

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

TEMPLATE_NAME = "kicad-project-template"


@celery.task(name="generate_kicad_project")
def generate_kicad_project(layout):
    from kle2netlist.skidl import kle2netlist
    from minio import Minio
    from minio.error import S3Error

    task_id = generate_kicad_project.request.id

    project_name = layout["meta"]["name"]
    project_name = "keyboard" if project_name == "" else project_name
    project_full_path = str(Path(task_id).joinpath(project_name).absolute())

    # 1. prepare project
    try:
        shutil.copytree(TEMPLATE_NAME, project_full_path)
    except OSError as e:
        print("Directory not copied. Aborting operation. Error: ", e)
        return False

    for f in Path(project_full_path).rglob(f"{TEMPLATE_NAME}*"):
        f.rename(f"{f.parent}/{project_name}{f.suffix}")

    layout_file = f"{project_full_path}/{project_name}_layout.json"
    print(layout_file)
    with open(layout_file, "w") as out:
        out.write(json.dumps(layout, indent=2))

    netlist_path = f"{project_full_path}/{project_name}.net"

    # this should be read from sym_lib_table:
    project_libs = [f"{project_full_path}/libs/MX_Alps_Hybrid/Schematic Library"]
    # 2. generate netlist
    # add error handling for this:
    kle2netlist(layout, netlist_path, additional_search_path=project_libs)

    ## 3. create .kicad_pcb from netlist
    env = os.environ.copy()
    env["KIPRJMOD"] = project_full_path
    pcb_path = f"{project_full_path}/{project_name}.kicad_pcb"
    p = subprocess.Popen(["kinet2pcb", "-w", "-nb", "-i", f"{project_name}.net"],
            cwd=project_full_path,
            env=env)
    p.communicate()

    # 4. arrange elements on pcb
    p = subprocess.Popen(["python3", "keyautoplace.py", "-l", f"{layout_file}", "-b" f"{pcb_path}"],
            env=env)
    p.communicate()

    # 5. move log data
    log_path = str(Path(task_id).joinpath("logs").absolute())
    os.mkdir(log_path)
    shutil.move("tasks.erc", log_path)
    shutil.move("tasks.log", log_path)
    shutil.move("tasks_lib_sklib.py", log_path)

    # 6. pack result
    shutil.make_archive(task_id, "zip", task_id)

    # 7. upload to storage
    client = Minio(
        "minio:9000",
        access_key="minio_dev",
        secret_key="minio_dev_secret",
        secure=False
    )

    try:
        bucket_name = "kicad-projects"
        found = client.bucket_exists(bucket_name)
        if not found:
            client.make_bucket(bucket_name)

        client.fput_object(bucket_name, f"{task_id}.zip", f"/home/user/{task_id}.zip")
    except S3Error as e:
        print("Data upload failed. Error:", e)

    # 8. clean up
    shutil.rmtree(task_id)
    os.remove(f"{task_id}.zip")

    return True
