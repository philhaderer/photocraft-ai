"""Manual check: does drag and drop (tkinterdnd2) work with YOUR Python? Not part of run_all.py. Run on Windows with the
Python the plugin uses (the line in data\\python.txt):

    "<that python.exe>" tests\\live_dnd.py

It installs tkinterdnd2 into a throw-away folder (%TEMP%\\pccomfy-dnd2-test, `pip install --target`), NOT into your
Python or the .venv, loads it from there and opens a small window. Drag a picture file from Explorer onto the window:
the window shows the path; the console prints it. Close the window to finish. Delete the folder whenever you like."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

target = Path(tempfile.gettempdir()) / "pccomfy-dnd2-test"
print("Python:", sys.executable, sys.version.split()[0])
try:
    import tkinter as tk
except ImportError as e:
    raise SystemExit(f"This Python has no tkinter: {e}")
if not (target / "tkinterdnd2").exists():
    print("Installing tkinterdnd2 into", target)
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target), "tkinterdnd2"])
    if r.returncode:
        raise SystemExit("pip could not install tkinterdnd2 (see above).")
sys.path.insert(0, str(target))
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception as e:
    raise SystemExit(f"tkinterdnd2 cannot be imported: {e}")

root = tk.Tk()                                   # a plain Tk window, like the plugin's: the package is loaded into it
try:
    version = TkinterDnD._require(root)
except Exception as e:
    root.destroy()
    raise SystemExit(f"tkdnd cannot be loaded into Tk: {e}")
print("tkdnd loaded, version", version)
root.title("Drop test")
root.geometry("360x160")
label = tk.Label(root, text="Drop a picture file here", bg="#404040", fg="#eeeeee", wraplength=330)
label.pack(fill="both", expand=True, padx=10, pady=10)


def drop(event):
    paths = root.tk.splitlist(event.data)
    print("dropped:", paths)
    label.configure(text="\n".join(paths))
    return event.action


label.drop_target_register(DND_FILES)
label.dnd_bind("<<Drop>>", drop)
print("OK so far: now drag a file onto the window (close it to finish).")
root.mainloop()
