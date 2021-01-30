import base64
import io
import json
import os
import requests

from celery.result import AsyncResult
from flask import Flask, jsonify, request, Response, stream_with_context
from minio import Minio
from tasks import generate_kicad_project


app = Flask(__name__)

minio_access_key = os.environ.get("MINIO_ACCESS_KEY", "minio_dev")
minio_secret_key = os.environ.get("MINIO_SECRET_KEY", "minio_dev_secret")

minio_client = Minio(
    "minio:9000",
    access_key=minio_access_key,
    secret_key=minio_secret_key,
    secure=False,
)


@app.route("/api/pcb", methods=["POST"])
def pcb():
    task_request = json.loads(request.data)
    task = generate_kicad_project.delay(task_request)
    return jsonify({"task_id": task.id}), 202


@app.route("/api/pcb/<task_id>", methods=["GET"])
def get_status(task_id):
    task_result = AsyncResult(task_id)

    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result,
    }
    return jsonify(result), 200


@app.route("/api/pcb/<task_id>/render", methods=["GET"])
def get_render(task_id):
    memory_file = io.BytesIO()
    data = minio_client.get_object("kicad-projects", f"{task_id}/front.svg")
    for data_chunk in data.stream(32 * 1024):
        memory_file.write(data_chunk)
    memory_file.seek(0)

    return base64.b64encode(memory_file.read()).decode()


@app.route("/api/pcb/<task_id>/result", methods=["GET"])
def get_result(task_id):
    url = minio_client.presigned_get_object(
        "kicad-projects", f"{task_id}/{task_id}.zip"
    )
    req = requests.get(url, stream=True)

    response = Response(stream_with_context(req.iter_content(chunk_size=2048)))
    response.headers["Content-Type"] = req.headers["content-type"]
    response.headers["Content-Disposition"] = f'attachment; filename="{task_id}.zip"'

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0")
