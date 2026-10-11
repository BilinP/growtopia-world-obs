#!/bin/bash
# Double-click this file in Finder to start Growtopia World -> OBS on macOS.
# First run sets up a private Python environment (.venv) with the dependencies.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/macos/"
  read -r -p "Press Enter to close."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First run: installing dependencies..."
  python3 -m venv .venv && .venv/bin/python -m pip install --quiet --upgrade pip \
    && .venv/bin/python -m pip install --quiet -r requirements.txt || {
      rm -rf .venv
      echo "Setup failed - see the messages above."
      read -r -p "Press Enter to close."
      exit 1
    }
fi

if ! .venv/bin/python -c "import tkinter; tkinter.Tk().destroy()" >/dev/null 2>&1; then
  echo "This Python has no working Tk (the window toolkit)."
  echo "Install Python from https://www.python.org/downloads/macos/ (it includes Tk), then"
  echo "delete the .venv folder here and double-click this file again."
  read -r -p "Press Enter to close."
  exit 1
fi

exec .venv/bin/python stream-growtopia-world.py "$@"
