"""Tests for gtworld. No OBS or Growtopia needed.

    python tests/test_gtworld.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gtworld  # noqa: E402

LOAD = "World::Load: Version 27. f: 64, Name: {}\n"


def temp_log(text):
    path = Path(tempfile.mkdtemp()) / "log.txt"
    path.write_text(text)
    return path


def test_parser():
    d = gtworld.detect_state
    assert d([LOAD.format("STARTWORLD")]) == "STARTWORLD"
    # Leaving to the world-select menu
    assert d([LOAD.format("STARTWORLD"),
              "[Controllers] CreateScreen: WorldSelectScreen\n",
              "[Controllers] Destroy: WorldScreen\n"]) == "MENU"
    # Warping world -> world: the old WorldScreen is destroyed after the new load
    assert d([LOAD.format("STARTWORLD"), LOAD.format("NEXTWORLD"),
              "[Controllers] CreateScreen: WorldScreen\n",
              "[Controllers] Destroy: WorldScreen\n"]) == "NEXTWORLD"
    assert d([LOAD.format("OTHERWORLD"), "[Controllers] Destroy: WorldSelectScreen\n"]) == "OTHERWORLD"
    assert d(["nothing relevant\n"]) is None


def test_non_utf8_log():
    path = Path(tempfile.mkdtemp()) / "log.txt"
    path.write_bytes(b"junk \xa7 byte\n" + LOAD.format("ABC").encode())
    assert gtworld.detect_state(gtworld.read_log_lines(path)) == "ABC"


def test_failed_update_is_retried():
    calls, fail = [], [True]
    w = gtworld.LogWatcher(temp_log(LOAD.format("ABC")), lambda t: calls.append(t) or not fail[0])
    w.check()
    assert w.last is None  # failed -> not recorded
    fail[0] = False
    w.check()
    assert w.last == "ABC"
    w.check()
    assert calls == ["ABC", "ABC"]  # no resend once it worked
    w.last = None
    w.check()
    assert len(calls) == 3  # forced resend (e.g. switched source)


def test_offline_placeholder():
    calls = []
    w = gtworld.LogWatcher(temp_log(LOAD.format("ABC")), calls.append)
    assert w.offline_text == gtworld.DEFAULT_CONFIG["offline_text"] == "NOT IN GAME"
    w.check()
    w.set_game_running(False)
    assert calls[-1] == "NOT IN GAME"
    w.check()  # log writes while closed don't override it
    assert calls == ["ABC", "NOT IN GAME"]
    w.set_game_running(None)  # unknown counts as open
    assert calls[-1] == "ABC"


def test_growtopia_check_returns_bool():
    assert gtworld.is_growtopia_running() in (True, False)


def test_macos_log_detection():
    home = Path(tempfile.mkdtemp())
    saved = (gtworld.sys.platform, os.environ.get("HOME"), os.environ.get("USERPROFILE"))
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
    gtworld.sys.platform = "darwin"
    try:
        lib = home / "Library"
        assert gtworld.default_log_path() == lib / "Application Support/Growtopia/log.txt"
        sandboxed = lib / "Containers/com.example.Growtopia/Data/Library/Application Support/Growtopia/log.txt"
        sandboxed.parent.mkdir(parents=True)
        sandboxed.write_text("x")
        assert gtworld.default_log_path() == sandboxed
        plain = lib / "Application Support/Growtopia/log.txt"
        plain.parent.mkdir(parents=True)
        time.sleep(0.05)
        plain.write_text("x")  # most recently written wins
        assert gtworld.default_log_path() == plain
        assert gtworld.obs_websocket_config_path() == \
            lib / "Application Support/obs-studio/plugin_config/obs-websocket/config.json"
    finally:
        gtworld.sys.platform = saved[0]
        for key, value in zip(("HOME", "USERPROFILE"), saved[1:]):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_launch_at_login_roundtrip():
    # Uses its own entry name so a real "Open when I log in" setting is never touched.
    name = "GrowtopiaWorldOBS-test"
    home = tempfile.mkdtemp()
    saved = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME")}
    os.environ["HOME"] = home  # macOS/Linux write a file under the home folder
    os.environ.pop("XDG_CONFIG_HOME", None)
    script = Path(__file__).resolve().parent.parent / "stream-growtopia-world.py"
    try:
        gtworld.set_launch_at_login(False, script, name=name)
        assert not gtworld.launch_at_login_enabled(name)
        gtworld.set_launch_at_login(True, script, name=name)
        assert gtworld.launch_at_login_enabled(name)
        gtworld.set_launch_at_login(False, script, name=name)
        assert not gtworld.launch_at_login_enabled(name)
    finally:
        gtworld.set_launch_at_login(False, script, name=name)
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_launch_command_starts_minimised():
    cmd = gtworld._launch_command("stream-growtopia-world.py")
    assert cmd[-1] == "--minimized" and cmd[-2].endswith("stream-growtopia-world.py")


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} tests passed")
