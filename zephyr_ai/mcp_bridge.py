from flask import Flask, request, jsonify
from zephyr_ai.core.utils import build_subprocess_env
import subprocess

app = Flask(__name__)


@app.route("/build", methods=["POST"])
def build():
    data = request.json
    board = data["board"]
    path = data["path"]

    result = subprocess.run(
        ["west", "build", "-b", board, path],
        capture_output=True,
        text=True
        ,
        env=build_subprocess_env(),
        check=False,
    )

    return jsonify({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    })


if __name__ == "__main__":
    app.run(port=5001)
