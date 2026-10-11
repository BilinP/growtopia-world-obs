"""Growtopia World -> OBS: shows the world you're in as an OBS text source.

    python stream-growtopia-world.py              # setup window
    python stream-growtopia-world.py --headless   # run with saved settings, no window
"""
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import gtworld

OBS_HELP = "In OBS: Tools → WebSocket Server Settings → tick 'Enable WebSocket server'."


def run_in_background(root, work, done):
    """Run work() off the UI thread, then call done(result, error) on the UI thread."""
    def target():
        try:
            result, error = work(), None
        except Exception as e:  # shown to the user, not raised
            result, error = None, e
        root.after(0, lambda: done(result, error))
    threading.Thread(target=target, daemon=True).start()


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = gtworld.load_config()
        self.obs = None
        self.watcher = None

        root.title("Growtopia World → OBS")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        pad = {"padx": 8, "pady": 4}

        # --- 1. OBS connection ---
        f1 = ttk.LabelFrame(root, text=" 1. Connect to OBS ")
        f1.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.host = tk.StringVar(value=self.cfg["obs_host"])
        self.port = tk.StringVar(value=str(self.cfg["obs_port"]))
        self.password = tk.StringVar(value=self.cfg["obs_password"])
        self.show_pw = tk.BooleanVar(value=False)

        ttk.Label(f1, text="Host").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f1, textvariable=self.host, width=22).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f1, text="Port").grid(row=0, column=2, sticky="e", **pad)
        ttk.Entry(f1, textvariable=self.port, width=7).grid(row=0, column=3, sticky="w", **pad)
        ttk.Label(f1, text="Password").grid(row=1, column=0, sticky="w", **pad)
        self.pw_entry = ttk.Entry(f1, textvariable=self.password, width=22, show="•")
        self.pw_entry.grid(row=1, column=1, sticky="w", **pad)
        ttk.Checkbutton(f1, text="Show", variable=self.show_pw,
                        command=lambda: self.pw_entry.config(show="" if self.show_pw.get() else "•")
                        ).grid(row=1, column=2, columnspan=2, sticky="w", **pad)
        btns = ttk.Frame(f1)
        btns.grid(row=2, column=0, columnspan=4, sticky="w", **pad)
        ttk.Button(btns, text="Auto-detect from OBS", command=self.auto_detect).pack(side="left")
        self.connect_btn = ttk.Button(btns, text="Connect", command=self.connect)
        self.connect_btn.pack(side="left", padx=6)
        self.obs_status = ttk.Label(f1, text="Not connected", foreground="gray", wraplength=380)
        self.obs_status.grid(row=3, column=0, columnspan=4, sticky="w", **pad)

        # --- 2. Text source ---
        f2 = ttk.LabelFrame(root, text=" 2. OBS text source ")
        f2.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.source = tk.StringVar(value=self.cfg["source_name"])
        self.source_box = ttk.Combobox(f2, textvariable=self.source, width=24)
        self.source_box.grid(row=0, column=0, sticky="w", **pad)
        self.create_btn = ttk.Button(f2, text="Create in current scene", command=self.create_source,
                                     state="disabled")
        self.create_btn.grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f2, text="Pick an existing text source, or type a name and create it.",
                  foreground="gray").grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        # --- 3. Growtopia log ---
        f3 = ttk.LabelFrame(root, text=" 3. Growtopia log file ")
        f3.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.log_path = tk.StringVar(value=self.cfg["log_path"])
        ttk.Entry(f3, textvariable=self.log_path, width=44).grid(row=0, column=0, sticky="w", **pad)
        ttk.Button(f3, text="Browse…", command=self.browse_log).grid(row=0, column=1, **pad)
        self.log_status = ttk.Label(f3, text="", foreground="gray")
        self.log_status.grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        self.log_path.trace_add("write", lambda *_: self.check_log_path())
        self.check_log_path()

        # --- Run ---
        f4 = ttk.Frame(root)
        f4.grid(row=3, column=0, sticky="ew", padx=10, pady=(6, 10))
        self.world = ttk.Label(f4, text="—", font=("Segoe UI", 22, "bold"))
        self.world.pack(side="left")
        self.start_btn = ttk.Button(f4, text="Save && Start", command=self.toggle)
        self.start_btn.pack(side="right")

        # First run: fill in OBS's settings for the user. Then try connecting straight away.
        if not gtworld.CONFIG_PATH.exists():
            self.auto_detect()
        self.connect()

    # --- helpers ---
    def set_status(self, label, text, color):
        label.config(text=text, foreground=color)

    def current_cfg(self):
        try:
            port = int(self.port.get())
        except ValueError:
            port = 4455
        return {
            "obs_host": self.host.get().strip() or "localhost",
            "obs_port": port,
            "obs_password": self.password.get(),
            "source_name": self.source.get().strip(),
            "log_path": self.log_path.get().strip(),
            "menu_text": self.cfg.get("menu_text", "MENU"),
        }

    def check_log_path(self):
        if Path(self.log_path.get()).is_file():
            self.set_status(self.log_status, "✔ Log file found", "green")
        else:
            self.set_status(self.log_status, "✖ File not found — open Growtopia once, or browse to log.txt",
                            "red")

    # --- actions ---
    def auto_detect(self):
        found = gtworld.detect_obs_settings()
        if not found:
            self.set_status(self.obs_status, "Couldn't find OBS WebSocket settings (needs OBS 28+). "
                            + OBS_HELP, "red")
            return
        self.host.set("localhost")
        self.port.set(str(found["obs_port"]))
        self.password.set(found["obs_password"])
        if found["server_enabled"]:
            self.set_status(self.obs_status, "Settings detected from OBS. Click Connect.", "gray")
        else:
            self.set_status(self.obs_status, "Settings detected, but the server is off. " + OBS_HELP, "red")

    def connect(self):
        cfg = self.current_cfg()
        if self.watcher:
            self.stop()
        if self.obs:
            self.obs.disconnect()
            self.obs = None
        obs = gtworld.OBS(cfg["obs_host"], cfg["obs_port"], cfg["obs_password"])
        self.connect_btn.config(state="disabled")
        self.set_status(self.obs_status, "Connecting…", "gray")

        def work():
            obs.connect()
            return obs.text_sources()

        def done(sources, error):
            self.connect_btn.config(state="normal")
            if error:
                obs.disconnect()
                self.create_btn.config(state="disabled")
                self.set_status(self.obs_status, f"Couldn't connect: {error}\nMake sure OBS is open. "
                                + OBS_HELP, "red")
                return
            self.obs = obs
            self.create_btn.config(state="normal")
            self.source_box["values"] = sources
            if not self.source.get() and sources:
                self.source.set(sources[0])
            msg = f"✔ Connected to OBS ({len(sources)} text source(s) found)."
            if self.source.get() not in sources:
                msg += f" '{self.source.get()}' doesn't exist yet — click 'Create in current scene'."
            self.set_status(self.obs_status, msg, "green")

        run_in_background(self.root, work, done)

    def create_source(self):
        name = self.source.get().strip() or "WorldText"
        self.source.set(name)
        if name in self.source_box["values"]:
            self.set_status(self.obs_status, f"'{name}' already exists — you're good.", "green")
            return

        def done(scene, error):
            if error:
                self.set_status(self.obs_status, f"Couldn't create source: {error}", "red")
                return
            self.source_box["values"] = (*self.source_box["values"], name)
            self.set_status(self.obs_status, f"✔ Created '{name}' in scene '{scene}'. "
                            "Style and position it in OBS.", "green")

        run_in_background(self.root, lambda: self.obs.create_text_source(name), done)

    def browse_log(self):
        path = filedialog.askopenfilename(title="Find Growtopia's log.txt",
                                          filetypes=[("Log file", "log.txt"), ("All files", "*.*")])
        if path:
            self.log_path.set(path)

    def toggle(self):
        if self.watcher:
            self.stop()
        else:
            self.start()

    def start(self):
        cfg = self.current_cfg()
        if not self.obs:
            self.set_status(self.obs_status, "Connect to OBS first (step 1).", "red")
            return
        if not cfg["source_name"]:
            self.set_status(self.obs_status, "Choose a text source (step 2).", "red")
            return
        if not Path(cfg["log_path"]).is_file():
            return
        gtworld.save_config(cfg)
        self.cfg = cfg
        obs = self.obs

        def on_change(text):  # runs on the watcher thread
            try:
                obs.set_text(cfg["source_name"], text)
                ok = True
            except Exception as e:
                ok = False
                print(f"Error updating OBS: {e}")
            self.root.after(0, lambda: self.show_world(text, ok))

        self.watcher = gtworld.LogWatcher(cfg["log_path"], on_change, cfg["menu_text"])
        self.start_btn.config(text="Stop")
        run_in_background(self.root, self.watcher.start, lambda _, err: err and print(err))

    def show_world(self, text, ok):
        if not self.watcher:
            return
        self.world.config(text=text)
        if ok:
            self.set_status(self.obs_status, f"✔ Live — '{self.cfg['source_name']}' shows: {text}", "green")
        else:
            self.set_status(self.obs_status, f"Couldn't update '{self.cfg['source_name']}' in OBS. "
                            "Is OBS still open and does the source exist?", "red")

    def stop(self):
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        self.start_btn.config(text="Save && Start")
        self.world.config(text="—")

    def on_close(self):
        self.stop()
        if self.obs:
            self.obs.disconnect()
        self.root.destroy()


def run_headless():
    """Use the settings saved by the setup window; no UI."""
    import time
    if not gtworld.CONFIG_PATH.exists():
        sys.exit("No config.json yet — run without --headless once to set things up.")
    cfg = gtworld.load_config()
    obs = gtworld.OBS(cfg["obs_host"], cfg["obs_port"], cfg["obs_password"])
    obs.connect()
    print(f"Connected to OBS. Watching {cfg['log_path']}  (Ctrl+C to stop)")

    def on_change(text):
        print(f"[UPDATE] {text}")
        try:
            obs.set_text(cfg["source_name"], text)
        except Exception as e:
            print(f"Error updating OBS: {e}")

    watcher = gtworld.LogWatcher(cfg["log_path"], on_change, cfg["menu_text"])
    watcher.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
        obs.disconnect()


if __name__ == "__main__":
    if "--headless" in sys.argv:
        run_headless()
    else:
        root = tk.Tk()
        App(root)
        root.mainloop()
