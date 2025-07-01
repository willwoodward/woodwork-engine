from flask import Flask, send_from_directory
import threading
import subprocess
import sys
import shutil
import webbrowser


class GUI:
    """
    A class to represent a developer GUI for Woodwork Engine.
    """

    def __init__(self):
        """Initialize the GUI."""
        self.app = Flask(__name__, static_folder="dist", static_url_path="")
        self.port = 43000

        @self.app.route("/")
        def serve_index():
            return send_from_directory(self.app.static_folder, "index.html")

        @self.app.route("/<path:path>")
        def serve_static(path):
            return send_from_directory(self.app.static_folder, path)

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
