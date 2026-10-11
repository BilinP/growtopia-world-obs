# Growtopia World → OBS

Shows the name of the Growtopia world you're in as a text source in OBS. It updates
automatically when you join a world, warp to another one, or go back to the menu,
and shows `NOT IN GAME` while Growtopia is closed.

It works by reading Growtopia's own `log.txt`. It does **not** touch the game,
inject anything, or read game memory.

## Download (no install needed)

Get the app for your computer from the
**[latest release](https://github.com/BilinP/growtopia-world-obs/releases/latest)** (under **Assets**):

| Computer | Download |
|---|---|
| Windows 10/11 | `GrowtopiaWorldOBS-vX.Y.Z-windows.exe` |
| Mac with Apple chip (M1 or newer) | `GrowtopiaWorldOBS-vX.Y.Z-macos-apple-silicon.zip` |
| Mac with Intel chip | `GrowtopiaWorldOBS-vX.Y.Z-macos-intel.zip` |

No Python or anything else to install. You also need
[OBS Studio 28+](https://obsproject.com/) and Growtopia.

**First launch:** the app isn't signed with a paid developer certificate, so your computer warns you once.

- **Windows:** if you see "Windows protected your PC", click **More info** → **Run anyway**.
- **macOS:** unzip it, drag **Growtopia World OBS** into **Applications** and open it. If macOS says it
  can't be opened, go to **System Settings → Privacy & Security**, scroll down and click **Open Anyway**.

## Setup

1. **Turn on OBS's WebSocket server:** in OBS go to **Tools → WebSocket Server Settings** and
   tick **Enable WebSocket server**. Keep authentication on.
2. **Open the app** (Growtopia World OBS).
3. A setup window opens:
   - **1. Connect to OBS:** your OBS port and password are filled in automatically from OBS's
     settings, and it connects for you. If not, click **Auto-detect from OBS** or type them in
     (OBS shows them under **Show Connect Info**), then click **Connect**.
   - **2. OBS text source:** pick an existing text source, or leave the name as `WorldText` and
     click **Create in current scene**. Then style and position the text in OBS as you like.
   - **When Growtopia is closed, show:** the placeholder text for when the game isn't open
     (`NOT IN GAME` by default). Change it any time; it applies straight away.
   - **3. Growtopia:** shows whether the game is open. The log file is found automatically.
     If it shows ✖, open Growtopia once, or click **Browse…** and pick `log.txt` from your
     Growtopia folder:
     - Windows: `%LOCALAPPDATA%\Growtopia\log.txt`
     - macOS: the app checks `~/Library/Application Support/Growtopia/`, `~/Library/Growtopia/` and the
       Growtopia app container under `~/Library/Containers/`. If yours is somewhere else, use
       **Browse…** (press **Cmd+Shift+.** in the file picker to show hidden folders like `Library`)
       and please open an issue saying where it was.
4. Click **Save & Start**. The window and your OBS text now show your current world (or `MENU`).

Your settings are saved automatically (see [Settings](#settings) for where), so next time you can just start the app and click **Save & Start**.

### Run without the window

When running from source, after setting up once you can run it in a terminal without the window:

```
python stream-growtopia-world.py --headless
```

On macOS: `./start-mac.command --headless`

### Settings

`config.json` is created by the setup window. You can also edit it by hand. It's saved in:

- App on Windows: `%APPDATA%\Growtopia World OBS\config.json`
- App on macOS: `~/Library/Application Support/Growtopia World OBS/config.json`
- Running from source: next to the script

| Key            | Meaning                                         | Default       |
|----------------|-------------------------------------------------|---------------|
| `obs_host`     | Where OBS is running                            | `localhost`   |
| `obs_port`     | OBS WebSocket port                              | `4455`        |
| `obs_password` | OBS WebSocket password                          | *(empty)*     |
| `source_name`  | OBS text source to update                       | `WorldText`   |
| `log_path`     | Path to Growtopia's `log.txt`                   | auto-detected |
| `menu_text`    | Text shown when you're not in a world           | `MENU`        |
| `offline_text` | Text shown while Growtopia is closed            | `NOT IN GAME` |

`config.json` contains your OBS password, so don't share it (it's in `.gitignore`).

## Run from source (developers)

Needs [Python 3.7+](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"**
in the installer. On macOS, use the python.org installer: it includes Tk, which the window needs, and
Apple's built-in `python3` often doesn't.

- **Windows:** `pip install -r requirements.txt`, then `python stream-growtopia-world.py`
- **macOS:** double-click **`start-mac.command`**. It sets everything up on first run (if macOS blocks
  it, right-click → **Open**).

To build the app yourself: `pip install pyinstaller`, then `python packaging/build.py`
(the result is in `dist/`). The icon is drawn by `packaging/make_icon.py`.

## Testing without OBS

```
python test_overlay.py
```

(On macOS, after running `start-mac.command` once: `.venv/bin/python test_overlay.py`)

This checks the log parser, then opens a small always-on-top window that shows the world
the app currently detects. Join and leave worlds in Growtopia to see it change. Close the window to stop.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Couldn't connect" | Make sure OBS is open and the WebSocket server is enabled (Setup step 1). Check the port/password. |
| "Couldn't update … in OBS" | The text source was renamed or deleted. Pick or create it again in step 2. |
| Log file not found | Start Growtopia at least once, or use **Browse…** to find `log.txt`. |
| Text doesn't change | Growtopia only writes the log while it's running. Join a world and wait a second. |

## How it works

Growtopia writes lines like these to `log.txt`:

```
World::Load: Version 27. f: 64, Name: MYWORLD      → shows "MYWORLD"
[Controllers] CreateScreen: WorldSelectScreen      → shows "MENU"
```

The app watches the file and reads it from the bottom up. The newest of those lines decides what
is shown. Note that `Destroy: WorldScreen` is ignored on purpose: when you warp between worlds,
the game destroys the *old* world's screen after the new world has already loaded.

## Running the tests

```
python tests/test_gtworld.py
```

## Releases

A new release is published automatically: every day at 12:00 UTC, GitHub Actions checks whether
anything was pushed to `main` since the last release. If so, it runs the tests on Windows, macOS
and Linux and publishes the next version (`v1.0.0` → `v1.0.1` → …) with a changelog and a
download ZIP. Pushing a tag like `v1.1.0` publishes that version immediately, and the workflow can
also be run by hand from the **Actions** tab.

## Disclaimer

This is a fan-made tool. It is not affiliated with or endorsed by Growtopia, Ubisoft, or OBS.

## License

[Apache 2.0](LICENSE)
