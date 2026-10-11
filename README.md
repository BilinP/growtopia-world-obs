# Growtopia World → OBS

Shows the name of the Growtopia world you're in as a text source in OBS. It updates
automatically when you join a world, warp to another one, or go back to the menu,
and shows `NOT IN GAME` while Growtopia is closed.

It works by reading Growtopia's own `log.txt`. It does **not** touch the game,
inject anything, or read game memory.

## Requirements

- Windows (macOS/Linux paths are included but untested)
- [Python 3.7+](https://www.python.org/downloads/) (tick **"Add python.exe to PATH"** in the installer)
- [OBS Studio 28+](https://obsproject.com/) (has the WebSocket server built in)
- Growtopia

## Install

1. Download this repo (**Code → Download ZIP**, then extract it) or `git clone` it.
2. Open a terminal in the folder and install the dependencies:

   ```
   pip install -r requirements.txt
   ```

## Setup

1. **Turn on OBS's WebSocket server:** in OBS go to **Tools → WebSocket Server Settings** and
   tick **Enable WebSocket server**. Keep authentication on.
2. **Start the app:**

   ```
   python stream-growtopia-world.py
   ```

3. A setup window opens:
   - **1. Connect to OBS:** your OBS port and password are filled in automatically from OBS's
     settings, and it connects for you. If not, click **Auto-detect from OBS** or type them in
     (OBS shows them under **Show Connect Info**), then click **Connect**.
   - **2. OBS text source:** pick an existing text source, or leave the name as `WorldText` and
     click **Create in current scene**. Then style and position the text in OBS as you like.
   - **When Growtopia is closed, show:** the placeholder text for when the game isn't open
     (`NOT IN GAME` by default). Change it any time; it applies straight away.
   - **3. Growtopia:** shows whether the game is open. The log file is found automatically.
     If it shows ✖, open Growtopia once, or click **Browse…** and pick `log.txt` from your Growtopia folder
     (usually `%LOCALAPPDATA%\Growtopia\log.txt`).
4. Click **Save & Start**. The window and your OBS text now show your current world (or `MENU`).

Your settings are saved to `config.json` next to the script, so next time you can just start the app and click **Save & Start**.

### Run without the window

After setting up once, you can run it in a terminal without the setup window:

```
python stream-growtopia-world.py --headless
```

### Settings

`config.json` is created by the setup window. You can also edit it by hand:

| Key            | Meaning                                         | Default       |
|----------------|-------------------------------------------------|---------------|
| `obs_host`     | Where OBS is running                            | `localhost`   |
| `obs_port`     | OBS WebSocket port                              | `4455`        |
| `obs_password` | OBS WebSocket password                          | *(empty)*     |
| `source_name`  | OBS text source to update                       | `WorldText`   |
| `log_path`     | Path to Growtopia's `log.txt`                   | auto-detected |
| `menu_text`    | Text shown when you're not in a world           | `MENU`        |
| `offline_text` | Text shown while Growtopia is closed            | `NOT IN GAME` |

`config.json` contains your OBS password. It's in `.gitignore`, so don't share it.

## Testing without OBS

```
python test_overlay.py
```

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

## Disclaimer

This is a fan-made tool. It is not affiliated with or endorsed by Growtopia, Ubisoft, or OBS.

## License

[Apache 2.0](LICENSE)
