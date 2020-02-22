import json

from celery.result import AsyncResult
from flask import Flask, jsonify, request

from tasks import generate_kicad_project


app = Flask(__name__)

@app.route('/api/pcb', methods=['POST'])
def pcb():
    layout = json.loads(request.data)
    task = generate_kicad_project.delay(layout)
    return jsonify({"task_id": task.id}), 202


@app.route('/api/pcb/<task_id>', methods=['GET'])
def get_status(task_id):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return jsonify(result), 200


@app.route('/api/pcb/<task_id>/result', methods=['GET'])
def get_result():
    pass


if __name__ == "__main__":
    app.run(host='0.0.0.0')
