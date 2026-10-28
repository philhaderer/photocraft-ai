"""Starts PhotoCraft with the control channel for the ComfyUI bridge, then opens the bridge window: the starter .bat
without a console window (run by the desktop shortcut; see pccomfy/launcher.py).
    pythonw photocraft-ai.pyw --photocraft "C:\\path\\to\\photocraft.exe" """
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from pccomfy import launcher  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--photocraft", default=os.environ.get("PHOTOCRAFT", ""), help="path to photocraft.exe")
sys.exit(launcher.launch(ap.parse_args().photocraft))
