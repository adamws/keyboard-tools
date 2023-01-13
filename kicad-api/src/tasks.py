import os
import shutil
import traceback

from celery import Celery, states
from celery.exceptions import Ignore
from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from pathlib import Path

from . import kicad

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
                    rule_filter=Filter(prefix=""),
                    rule_id="expire",
                    expiration=Expiration(days=1),
                ),
            ],
        )
        client.set_bucket_lifecycle("kicad-projects", config)

    home = Path.home()
    client.fput_object(
        bucket_name, f"{task_id}/{task_id}.zip", f"{home}/{task_id}.zip"
    )
    client.fput_object(
        bucket_name,
        f"{task_id}/front.svg",
        f"{log_path}/front.svg",
        content_type="image/svg+xml",
    )


@celery.task(name="generate_kicad_project")
def generate_kicad_project(task_request):
    task_id = generate_kicad_project.request.id
    try:
        log_path = kicad.new_pcb(task_id, task_request, __update_percentage)
        __upload_to_storage(task_id, log_path)
    except Exception as err:
        generate_kicad_project.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(err).__name__,
                "exc_message": traceback.format_exc(limit=None),
            },
        )
        raise Ignore() from err
    finally:
        shutil.rmtree(task_id, ignore_errors=True)
        zipfile = f"{task_id}.zip"
        if os.path.isfile(zipfile):
            os.remove(zipfile)

    return {"percentage": 100}
