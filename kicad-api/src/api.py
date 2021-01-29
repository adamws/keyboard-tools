import base64
import io
import json
import os

from celery.result import AsyncResult
from flask import Flask, jsonify, request, send_file
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
    layout = json.loads(request.data)
    task = generate_kicad_project.delay(layout)
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
    for d in data.stream(32 * 1024):
        memory_file.write(d)
    memory_file.seek(0)

    return base64.b64encode(memory_file.read()).decode()


@app.route("/api/pcb/<task_id>/result", methods=["GET"])
def get_result(task_id):
    # although this works, perhaps it would be better to redirrect
    # GET directly to minio?
    memory_file = io.BytesIO()
    data = minio_client.get_object("kicad-projects", f"{task_id}/{task_id}.zip")
    for d in data.stream(32 * 1024):
        memory_file.write(d)
    memory_file.seek(0)

    return send_file(
        memory_file, attachment_filename=f"{task_id}.zip", as_attachment=True
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0")
