"""Core logic: read the Growtopia log, work out the current world, push it to OBS."""
import json
import os
import re
import sys
from pathlib import Path

from obswebsocket import obsws, requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "source_name": "WorldText",
    "log_path": "",
    "menu_text": "MENU",
}

# World name comes from the world load line.
WORLD_PATTERN = re.compile(r"World::Load:.*Name:\s*(\w+)", re.IGNORECASE)
# Note: "Destroy: WorldScreen" is NOT a menu signal - when warping between worlds
# the old world's screen is destroyed *after* the new world has loaded.
MENU_PATTERN = re.compile(r"CreateScreen:\s*(WorldSelectScreen|ConnectionScreen)", re.IGNORECASE)

# OBS text source kinds, newest first (Windows GDI+, then FreeType for macOS/Linux).
TEXT_INPUT_KINDS = ("text_gdiplus_v3", "text_gdiplus_v2", "text_gdiplus",
                    "text_ft2_source_v2", "text_ft2_source")


# === Paths & config ===

def default_log_path():
    env = os.getenv("GROWTOPIA_LOG_PATH") or os.getenv("GROWTOPIA_LOG")
    if env:
        return Path(env)
    if sys.platform.startswith("win"):
        return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Growtopia" / "log.txt"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Growtopia" / "log.txt"
    return Path.home() / ".growtopia" / "log.txt"


def obs_websocket_config_path():
    if sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"


def detect_obs_settings():
    """Read OBS's own WebSocket settings. Returns a dict, or None if not found."""
    path = obs_websocket_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "obs_port": int(data.get("server_port", 4455)),
        "obs_password": data.get("server_password", "") if data.get("auth_required", True) else "",
        "server_enabled": bool(data.get("server_enabled", False)),
    }


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if not cfg["log_path"]:
        cfg["log_path"] = str(default_log_path())
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def is_growtopia_running():
    """True if the Growtopia game process is running. None if it can't be checked."""
    import subprocess
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Growtopia.exe", "/NH"],
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return "growtopia.exe" in out.lower()
        return subprocess.run(["pgrep", "-ix", "growtopia"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None


# === Log parsing ===

def read_log_lines(path):
    """Read the log. Growtopia writes non-UTF-8 bytes, so don't fail on them."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def detect_state(lines, menu_text="MENU"):
    """Return the current world name, menu_text if at the menu, or None."""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        if MENU_PATTERN.search(line):
            return menu_text
        match = WORLD_PATTERN.search(line)
        if match:
            return match.group(1)
    return None


# === OBS ===

class OBS:
    def __init__(self, host, port, password):
        self.ws = obsws(host, int(port), password, legacy=False, timeout=5)

    def connect(self):
        self.ws.connect()  # raises obswebsocket.exceptions.ConnectionFailure

    def disconnect(self):
        try:
            self.ws.disconnect()
        except Exception:
            pass

    def _call(self, request):
        resp = self.ws.call(request)
        if not resp.status:
            raise RuntimeError(resp.datain.get("comment") or f"{resp.name} failed")
        return resp.datain

    def text_sources(self):
        inputs = self._call(requests.GetInputList()).get("inputs", [])
        return [i["inputName"] for i in inputs
                if i.get("inputKind", "").startswith(("text_gdiplus", "text_ft2"))]

    def create_text_source(self, name, text="MENU"):
        """Create a text source showing `text` in the current scene."""
        kinds = self._call(requests.GetInputKindList(unversioned=False)).get("inputKinds", [])
        kind = next((k for k in TEXT_INPUT_KINDS if k in kinds), None)
        if not kind:
            raise RuntimeError("This OBS has no text source type available.")
        scene = self._call(requests.GetCurrentProgramScene())
        scene_name = scene.get("currentProgramSceneName") or scene.get("sceneName")
        self._call(requests.CreateInput(sceneName=scene_name, inputName=name, inputKind=kind,
                                        inputSettings={"text": text}, sceneItemEnabled=True))
        return scene_name

    def on_source_change(self, callback):
        """Call callback(event, data) when an input is created, removed or renamed in OBS.

        event is "InputCreated", "InputRemoved" or "InputNameChanged". Runs on the
        websocket thread.
        """
        def handler(event):
            name = type(event).__name__
            if name in ("InputCreated", "InputRemoved", "InputNameChanged"):
                callback(name, event.datain)
        self.ws.register(handler)

    def set_text(self, source, text):
        self._call(requests.SetInputSettings(inputName=source, inputSettings={"text": text}))


# === Log watcher ===

class _Handler(FileSystemEventHandler):
    def __init__(self, watcher):
        self.watcher = watcher

    def on_modified(self, event):
        if os.path.abspath(getattr(event, "src_path", "") or "") == os.path.abspath(self.watcher.log_path):
            self.watcher.check()


class LogWatcher:
    """Watches the log and calls on_change(text) whenever the world changes.

    If on_change returns False the update is treated as failed and retried on
    the next log write.
    """

    def __init__(self, log_path, on_change, menu_text="MENU"):
        self.log_path = str(log_path)
        self.on_change = on_change
        self.menu_text = menu_text
        self.last = None
        self.observer = None

    def check(self):
        try:
            state = detect_state(read_log_lines(self.log_path), self.menu_text) or self.menu_text
        except OSError as e:
            print(f"Error reading log: {e}")
            return
        if state != self.last and self.on_change(state) is not False:
            self.last = state

    def current_state(self):
        try:
            return detect_state(read_log_lines(self.log_path), self.menu_text) or self.menu_text
        except OSError:
            return self.menu_text

    def start(self):
        self.check()  # show the current state immediately
        self.observer = Observer()
        self.observer.schedule(_Handler(self), path=str(Path(self.log_path).parent), recursive=False)
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
