"""Core logic: read the Growtopia log, work out the current world, push it to OBS."""
import json
import os
import re
import sys
import threading
from pathlib import Path

from obswebsocket import obsws, requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

try:
    from _version import __version__  # written by the release build
except ImportError:
    __version__ = "dev"

APP_NAME = "Growtopia World OBS"


def _config_dir():
    """Next to the script when run from source; the user's app-data folder for the packaged app
    (its own folder is temporary on Windows and read-only on macOS)."""
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    if sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


CONFIG_PATH = _config_dir() / "config.json"


def resource_path(relative):
    """A file shipped with the app (inside the bundle when packaged)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative

DEFAULT_CONFIG = {
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "source_name": "WorldText",
    "log_path": "",
    "menu_text": "MENU",
    "offline_text": "NOT IN GAME",
    "auto_start": True,  # start tracking as soon as the app opens (once set up)
}

# World name comes from the world load line.
WORLD_PATTERN = re.compile(r"World::Load:.*Name:\s*(\w+)", re.IGNORECASE)
# Note: "Destroy: WorldScreen" is NOT a menu signal - when warping between worlds
# the old world's screen is destroyed *after* the new world has loaded.
MENU_PATTERN = re.compile(r"CreateScreen:\s*(WorldSelectScreen|ConnectionScreen)", re.IGNORECASE)

# A font that exists on each platform (Tk silently falls back if it doesn't).
UI_FONT = ("Segoe UI" if sys.platform.startswith("win")
           else "Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")

# OBS text source kinds, newest first (Windows GDI+, then FreeType for macOS/Linux).
TEXT_INPUT_KINDS = ("text_gdiplus_v3", "text_gdiplus_v2", "text_gdiplus",
                    "text_ft2_source_v2", "text_ft2_source")


# === Paths & config ===

def log_path_candidates():
    """Places Growtopia's log.txt may be, most likely first."""
    if sys.platform.startswith("win"):
        return [Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Growtopia" / "log.txt"]
    if sys.platform == "darwin":
        lib = Path.home() / "Library"
        found = [lib / "Application Support" / "Growtopia" / "log.txt",
                 lib / "Growtopia" / "log.txt",
                 lib / "Caches" / "Growtopia" / "log.txt",
                 lib / "Logs" / "Growtopia" / "log.txt"]
        # App Store / sandboxed builds keep their files inside a container.
        for parent in (lib / "Containers", lib / "Group Containers"):
            try:
                containers = [c for c in parent.iterdir() if "growtopia" in c.name.lower()]
            except OSError:
                containers = []
            for c in containers:
                found += [c / "Data" / "Library" / "Application Support" / "Growtopia" / "log.txt",
                          c / "Data" / "Library" / "Application Support" / "log.txt",
                          c / "Data" / "Documents" / "log.txt"]
        found.append(Path("/Applications/Growtopia.app/Contents/Resources/log.txt"))
        return found
    return [Path.home() / ".growtopia" / "log.txt"]


def default_log_path():
    """The env override, else the most recently written existing candidate, else the likeliest one."""
    env = os.getenv("GROWTOPIA_LOG_PATH") or os.getenv("GROWTOPIA_LOG")
    if env:
        return Path(env)
    candidates = log_path_candidates()
    existing = [p for p in candidates if p.is_file()]
    if existing:
        return max(existing, key=lambda p: p.stat().st_mtime)
    return candidates[0]


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
    if not cfg["log_path"] or not Path(cfg["log_path"]).is_file():
        detected = default_log_path()
        if not cfg["log_path"] or detected.is_file():
            cfg["log_path"] = str(detected)
    return cfg


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def is_growtopia_running():
    """True if the Growtopia game process is running. None if it can't be checked."""
    import subprocess
    # stdin=DEVNULL: the packaged Windows app has no console handles to inherit.
    opts = {"capture_output": True, "text": True, "timeout": 5, "stdin": subprocess.DEVNULL}
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Growtopia.exe", "/NH"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **opts).stdout
            return "growtopia.exe" in out.lower()
        if subprocess.run(["pgrep", "-ix", "growtopia"], **opts).returncode == 0:
            return True
        # macOS: match the app bundle's executable (process names can be truncated).
        return subprocess.run(["pgrep", "-if", r"growtopia\.app/contents/macos/"], **opts).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None


# === Open at login ===

LOGIN_ITEM_NAME = "GrowtopiaWorldOBS"


def _launch_command(script):
    """How to start this app minimised: the packaged executable, or Python + the script."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--minimized"]
    python = Path(sys.executable)
    if sys.platform.startswith("win") and (python.parent / "pythonw.exe").exists():
        python = python.parent / "pythonw.exe"  # no console window
    return [str(python), str(Path(script).resolve()), "--minimized"]


def _login_item_path(name):
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"com.growtopiaworldobs.{name}.plist"
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / f"{name}.desktop"


def launch_at_login_enabled(name=LOGIN_ITEM_NAME):
    if sys.platform.startswith("win"):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, name)
            return True
        except OSError:
            return False
    return _login_item_path(name).exists()


def set_launch_at_login(enabled, script, name=LOGIN_ITEM_NAME):
    """Add or remove this app from the programs that open when the user logs in."""
    cmd = _launch_command(script)
    if sys.platform.startswith("win"):
        import subprocess
        import winreg
        # CreateKeyEx also opens it; the Run key can be missing on a brand-new account.
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
        return
    path = _login_item_path(name)
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        import plistlib
        with open(path, "wb") as f:
            plistlib.dump({"Label": f"com.growtopiaworldobs.{name}", "ProgramArguments": cmd,
                           "RunAtLoad": True}, f)
    else:
        import shlex
        path.write_text("[Desktop Entry]\nType=Application\nName=Growtopia World OBS\n"
                        f"Exec={' '.join(shlex.quote(c) for c in cmd)}\n", encoding="utf-8")


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

    def ping(self):
        """Raises if OBS is no longer reachable."""
        self._call(requests.GetVersion())

    def set_text(self, source, text):
        self._call(requests.SetInputSettings(inputName=source, inputSettings={"text": text}))


# === Log watcher ===

class _Handler(FileSystemEventHandler):
    def __init__(self, watcher):
        self.watcher = watcher

    def on_modified(self, event):
        if _same_path(getattr(event, "src_path", "") or "", self.watcher.log_path):
            self.watcher.check()


def _same_path(a, b):
    # realpath: macOS reports some paths through symlinks; normcase: case-insensitive filesystems.
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class LogWatcher:
    """Watches the log and calls on_change(text) whenever the world changes.

    If on_change returns False the update is treated as failed and retried on
    the next log write. While the game is reported closed (set_game_running),
    offline_text is shown instead of the world.
    """

    def __init__(self, log_path, on_change, menu_text="MENU", offline_text="NOT IN GAME"):
        self.log_path = str(log_path)
        self.on_change = on_change
        self.menu_text = menu_text
        self.offline_text = offline_text
        self.game_running = True
        self.last = None
        self.observer = None
        self._lock = threading.Lock()  # check() runs on the watchdog and game-poll threads

    def set_game_running(self, running):
        """Tell the watcher whether Growtopia is open (None = unknown, treated as open)."""
        running = running is not False
        if running != self.game_running:
            self.game_running = running
            self.check()

    def check(self):
        with self._lock:
            self._check()

    def _check(self):
        if self.game_running:
            try:
                state = detect_state(read_log_lines(self.log_path), self.menu_text) or self.menu_text
            except OSError as e:
                print(f"Error reading log: {e}")
                return
        else:
            state = self.offline_text
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
