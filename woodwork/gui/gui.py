from flask import Flask, send_from_directory, request, jsonify
import threading
import subprocess
import sys
import shutil
import webbrowser
import os

from woodwork.core.task_master import task_master
from woodwork.types import Workflow


class GUI:
    """
    A class to represent a developer GUI for Woodwork Engine.
    """

    def __init__(self, task_master: task_master):
        """Initialize the GUI."""
        self.app = Flask(__name__, static_folder="dist", static_url_path="")
        self.port = 43000
        self.task_m = task_master

        @self.app.route("/api/components/list", methods=["GET"])
        def get_tools_list():
            return jsonify(list(map(lambda x: x.name, self.task_m._tools)))

        @self.app.route("/api/input", methods=["GET"])
        def get_output():
            """Input is sent and received from an API component."""
            return jsonify({"response": "hello, this is a test response."})

        @self.app.route("/api/workflows/get", methods=["GET"])
        def get_workflows():
            workflows = self.task_m.list_workflows()
            return jsonify([{"id": hash(workflow), "name": workflow} for workflow in workflows])

        @self.app.route("/api/workflows", methods=["POST"])
        def create_workflow():
            workflow_data = request.json
            if not workflow_data:
                return jsonify({"error": "No JSON payload provided"}), 400
            workflow = Workflow.from_dict(workflow_data)
            success = self.task_m.add_workflow(workflow)
            if success:
                return jsonify({"status": "success"}), 201
            else:
                return jsonify({"status": "error saving"}), 500

        @self.app.route("/", defaults={"path": ""})
        @self.app.route("/<path:path>")
        def serve_react(path):
            # If path starts with 'api/', return 404 (Flask will match actual routes)
            if path.startswith("api/"):
                return "Not Found", 404
            # Try to return the static file if it exists, otherwise return index.html for client-side routing
            file_path = "dist" + "/" + path
            if path != "" and os.path.exists(file_path):
                return send_from_directory("dist/", path)
            return send_from_directory("dist/", "index.html")

    def _try_open_browser(self):
        if sys.platform == "linux":
            if shutil.which("wslview"):
                subprocess.Popen(
                    ["wslview", f"http://localhost:{self.port}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return
        try:
            webbrowser.open(f"http://localhost:{self.port}")
        except:
            pass

    def run(self):
        """Run the GUI application."""
        threading.Timer(1.0, lambda: self._try_open_browser()).start()
        self.app.run(debug=False, port=self.port)
