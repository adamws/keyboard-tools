import os
import shutil
import traceback
from pathlib import Path

from celery import Celery, states
from celery.exceptions import Ignore
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from . import kicad

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379"
)

s3_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "s3_dev")
s3_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "s3_dev_secret")


def __update_percentage(percentage):
    generate_kicad_project.update_state(
        state="PROGRESS", meta={"percentage": percentage}
    )


def __upload_to_storage(task_id, log_path):
    client = boto3.client(
        "s3",
        endpoint_url="http://s3:9000",
        aws_access_key_id=s3_access_key,
        aws_secret_access_key=s3_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    bucket_name = "kicad-projects"
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError:
        client.create_bucket(Bucket=bucket_name)
        lifecycle_configuration = {
            "Rules": [
                {
                    "ID": "expire",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": 1},
                }
            ]
        }
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name, LifecycleConfiguration=lifecycle_configuration
        )

    home = Path.home()
    client.upload_file(f"{home}/{task_id}.zip", bucket_name, f"{task_id}/{task_id}.zip")
    for side in ["front", "back"]:
        client.upload_file(
            f"{log_path}/{side}.svg",
            bucket_name,
            f"{task_id}/{side}.svg",
            ExtraArgs={"ContentType": "image/svg+xml"},
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
