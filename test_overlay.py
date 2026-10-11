"""Live test without OBS.

Runs the real log watcher, but instead of sending the text to OBS it shows it
in a small always-on-top window. Enter/leave worlds in Growtopia and the window
should change to the world name / "MENU".

    python test_overlay.py
"""
import tkinter as tk

import gtworld


def self_check():
    """Sanity-check the parser on known log lines before going live."""
    d = gtworld.detect_state
    load = "World::Load: Version 27. f: 64, Name: {}\n"
    assert d([load.format("STARTWORLD")]) == "STARTWORLD"
    # Leaving to the world-select menu
    assert d([load.format("STARTWORLD"),
              "[Controllers] CreateScreen: WorldSelectScreen\n",
              "[Controllers] Destroy: WorldScreen\n"]) == "MENU"
    # Warping world -> world: old WorldScreen is destroyed after the new load
    assert d([load.format("STARTWORLD"), load.format("NEXTWORLD"),
              "[Controllers] CreateScreen: WorldScreen\n",
              "[Controllers] Destroy: WorldScreen\n"]) == "NEXTWORLD"
    assert d([load.format("OTHERWORLD"),
              "[Controllers] Destroy: WorldSelectScreen\n"]) == "OTHERWORLD"
    assert d(["nothing relevant\n"]) is None
    print("Parser self-check passed")


def main():
    self_check()
    log_path = gtworld.load_config()["log_path"]

    root = tk.Tk()
    root.title("WorldText test")
    root.attributes("-topmost", True)
    root.geometry("+40+40")
    root.configure(bg="black")
    tk.Label(root, text="WorldText (test)", fg="gray", bg="black",
             font=("Segoe UI", 9)).pack(padx=12, pady=(8, 0))
    label = tk.Label(root, text="...", fg="white", bg="black",
                     font=("Segoe UI", 28, "bold"))
    label.pack(padx=20, pady=(0, 12))

    def on_change(text):
        print(f"[UPDATE] {text}")
        # Called from the watcher thread; hand it to the Tk thread.
        label.after(0, lambda: label.config(text=text))

    watcher = gtworld.LogWatcher(log_path, on_change)
    watcher.start()
    print(f"Watching {log_path} - close the window to stop.")
    try:
        root.mainloop()
    finally:
        watcher.stop()


if __name__ == "__main__":
    main()
