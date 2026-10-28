"""The watcher that starts the bridge window with PhotoCraft (no console window; see pccomfy/autostart.py).
Set up with: python -m pccomfy autostart install"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from pccomfy import autostart  # noqa: E402

sys.exit(autostart.watch())
