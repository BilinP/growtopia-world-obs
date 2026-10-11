"""Build the standalone app with PyInstaller (no Python needed by the people who use it).

    pip install -r requirements.txt pyinstaller
    python packaging/build.py [VERSION]

Windows -> dist/GrowtopiaWorldOBS.exe        (single file)
macOS   -> dist/Growtopia World OBS.app      (app bundle)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    (ROOT / "_version.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")

    sep = ";" if sys.platform.startswith("win") else ":"
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--add-data", f"{PKG / 'icon.png'}{sep}packaging",
        # These pick their platform-specific modules at runtime, so bundle them all.
        "--collect-submodules", "watchdog",
        "--collect-submodules", "obswebsocket",
        "--hidden-import", "_version",
        "--paths", str(ROOT),
    ]
    if sys.platform.startswith("win"):
        args += ["--onefile", "--name", "GrowtopiaWorldOBS", "--icon", str(PKG / "icon.ico")]
    elif sys.platform == "darwin":
        version_number = version.lstrip("v") if version != "dev" else "0.0.0"
        args += ["--name", "Growtopia World OBS", "--icon", str(PKG / "icon.icns"),
                 "--osx-bundle-identifier", "com.growtopiaworldobs.app"]
    else:
        args += ["--onefile", "--name", "growtopia-world-obs"]
    args.append(str(ROOT / "stream-growtopia-world.py"))

    print(" ".join(args))
    subprocess.run(args, check=True, cwd=ROOT)

    if sys.platform == "darwin":
        set_mac_version(ROOT / "dist" / "Growtopia World OBS.app", version_number)


def set_mac_version(app, number):
    """Show the real version in Finder's Get Info and allow dark mode."""
    import plistlib
    path = app / "Contents" / "Info.plist"
    with open(path, "rb") as f:
        info = plistlib.load(f)
    info["CFBundleShortVersionString"] = number
    info["CFBundleVersion"] = number
    info["NSRequiresAquaSystemAppearance"] = False
    with open(path, "wb") as f:
        plistlib.dump(info, f)
    # Editing Info.plist invalidates the signature; re-sign ad-hoc (required on Apple Silicon).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)


if __name__ == "__main__":
    main()
