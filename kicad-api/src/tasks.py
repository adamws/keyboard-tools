import io
import json
import os
import shutil
import traceback
import zipfile
from contextlib import contextmanager
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
# Use JSON serialization for task messages
celery.conf.task_serializer = "json"
celery.conf.accept_content = ["json"]
celery.conf.result_serializer = "json"

s3_endpoint = os.environ.get("S3_URL", "localhost:9000")
s3_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "s3_dev")
s3_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "s3_dev_secret")


@contextmanager
def create_zip_in_memory(source_dir):
    """Create a zip file in memory from a directory."""
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            source_path = Path(source_dir)
            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_path)
                    zip_file.write(file_path, arcname)
        zip_buffer.seek(0)
        yield zip_buffer
    finally:
        zip_buffer.close()


def __upload_to_storage(task_id, work_dir):
    client = boto3.client(
        "s3",
        endpoint_url="http://" + s3_endpoint,
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

    with create_zip_in_memory(work_dir) as zip_buffer:
        client.upload_fileobj(zip_buffer, bucket_name, f"{task_id}/{task_id}.zip")

    log_path = Path(work_dir) / "logs"
    for name in ["front", "back", "schematic"]:
        client.upload_file(
            f"{log_path}/{name}.svg",
            bucket_name,
            f"{task_id}/{name}.svg",
            ExtraArgs={"ContentType": "image/svg+xml"},
        )


@celery.task(name="generate_kicad_project")
def generate_kicad_project(task_request):
    if isinstance(task_request, str):
        task_request = json.loads(task_request)
    work_dir = None
    task_id = generate_kicad_project.request.id
    try:
        generate_kicad_project.update_state(
            state="PROGRESS",
            meta={"percentage": 0}
        )
        work_dir = kicad.new_pcb(task_id, task_request)
        __upload_to_storage(task_id, work_dir)
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
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)

    return {"percentage": 100}

