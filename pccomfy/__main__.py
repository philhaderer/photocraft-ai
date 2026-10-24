"""python -m pccomfy [gui|check|run] …"""

from __future__ import annotations

import argparse
import json
import sys

from . import config as cfgmod
from .bridge import MODES, Bridge, BridgeError, Request
from .comfy import ComfyError, ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError
from .workflows import GenParams


def make(cfg: dict) -> Bridge:
    pcc, cc = cfg["photocraft"], cfg["comfyui"]
    pc = PhotoCraft(pcc["host"], int(pcc["port"]), token_file=pcc["token_file"], headless=bool(pcc["headless"]))
    return Bridge(pc, ComfyUI(cc["url"]), pcc["exchange_dir"])


def cmd_check(cfg: dict) -> int:
    b = make(cfg)
    ok = True
    try:
        info = b.pc.ping()
        print(f"PhotoCraft: OK – open documents: {info['documents']}, active: {info['active']}")
    except PhotoCraftError as e:
        ok = False
        print(f"PhotoCraft: ERROR – {e}")
    try:
        stats = b.comfy.system_stats()
        dev = (stats.get("devices") or [{}])[0]
        print(f"ComfyUI: OK – {stats.get('system', {}).get('comfyui_version', '?')}, {dev.get('name', '?')}")
        ckpts = b.comfy.checkpoints()
        print(f"  checkpoints ({len(ckpts)}):", *ckpts[:30], sep="\n    ")
        fo = b.comfy.fooocus_inpaint()
        print("  Fooocus inpaint:", f"OK ({fo[0]}, {fo[1]})" if fo else "not found (needs comfyui-inpaint-nodes and the files in models/inpaint)")
    except ComfyError as e:
        ok = False
        print(f"ComfyUI: ERROR – {e}")
    return 0 if ok else 1


def cmd_probe(cfg: dict) -> int:
    """Debug: show what this PhotoCraft build answers on the control channel."""
    b = make(cfg)
    for label, fn in (("ui.inspect", lambda: b.pc.call("ui.inspect")),
                      ("session.inspect", lambda: b.pc.execute("session.inspect")),
                      ("document.inspect", lambda: b.pc.execute("document.inspect"))):
        try:
            res = fn()
            text = json.dumps(res, ensure_ascii=False)
            print(f"{label}: OK, top-level keys: {list(res) if isinstance(res, dict) else type(res).__name__}")
            print("   " + text[:600] + (" ..." if len(text) > 600 else ""))
        except PhotoCraftError as e:
            print(f"{label}: ERROR - {e}")
    return 0


def cmd_commands(cfg: dict, pattern: str) -> int:
    """Debug: look for PhotoCraft commands whose name matches `pattern` (e.g. "history|undo|group")."""
    import re
    b = make(cfg)
    found = None
    for method in ("engine.commands", "engine.list", "engine.listCommands", "commands.list", "engine.describe", "help"):
        try:
            res = b.pc.call(method)
        except PhotoCraftError as e:
            print(f"{method}: {str(e)[:100]}")
            continue
        names = []

        def walk(x):
            if isinstance(x, str):
                names.append(x)
            elif isinstance(x, dict):
                for k, v in x.items():
                    names.append(str(k))
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(res)
        found = names
        print(f"{method}: OK, {len(names)} names")
        break
    for probe in ("history.inspect", "history.list", "history.state", "document.history"):
        try:
            res = b.pc.execute(probe)
            print(f"{probe}: OK " + json.dumps(res, ensure_ascii=False)[:300])
        except PhotoCraftError as e:
            print(f"{probe}: {str(e)[:100]}")
    if found:
        rx = re.compile(pattern, re.I)
        for n in sorted({n for n in found if rx.search(n) and len(n) < 80}):
            print("  " + n)
    return 0


def cmd_run(cfg: dict, a) -> int:
    d = cfg["defaults"]
    p = GenParams(prompt=a.prompt, negative=a.negative if a.negative is not None else d["negative"],
                  checkpoint=a.checkpoint or d["checkpoint"], steps=a.steps or d["steps"],
                  cfg=a.cfg or d["cfg"], sampler=d["sampler"], scheduler=d["scheduler"], seed=a.seed,
                  denoise=a.denoise if a.denoise is not None else (1.0 if a.mode in ("inpaint", "remove", "reference", "outpaint") else d["denoise"]))
    req = Request(mode=a.mode, params=p, workflow=a.workflow, base_res=a.res or d["base_res"],
                  context=d["context"], mask_grow=d["mask_grow"], mask_blur=d["mask_blur"],
                  outpaint=tuple(a.expand), overlap=d["overlap"], variants=a.variants, fooocus=not a.no_fooocus,
                  layer_mask=a.layer_mask, enhance=not a.no_enhance,
                  ref_collage=not a.no_collage)
    b = make(cfg)
    if not p.checkpoint and not a.workflow:
        try:
            p.checkpoint = (b.comfy.checkpoints() or [""])[0]
        except ComfyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def progress(f, msg, **_kw):
        pct = "   " if f < 0 else f"{int(f * 100):3d}%"
        print(f"\r{pct} {msg:<50}", end="", flush=True)

    try:
        res = b.run(req, progress)
    except (BridgeError, ComfyError, ValueError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    print("\n" + json.dumps(res, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pccomfy", description="PhotoCraft ↔ ComfyUI bridge")
    ap.add_argument("--config", help="path to config.toml")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="bridge window (default)")
    sub.add_parser("check", help="check connections and list models")
    sub.add_parser("windows", help="debug: list PhotoCraft's windows (what the bridge window is tied to)")
    c = sub.add_parser("commands", help="debug: list PhotoCraft commands matching a pattern")
    c.add_argument("pattern", nargs="?", default="history|undo|group|transaction|step")
    sub.add_parser("probe", help="debug: print what PhotoCraft answers on the control channel")
    r = sub.add_parser("run", help="one generation from the command line")
    r.add_argument("mode", choices=MODES)
    r.add_argument("-p", "--prompt", default="")
    r.add_argument("-n", "--negative")
    r.add_argument("-m", "--checkpoint")
    r.add_argument("-w", "--workflow", help="custom workflow (API-format JSON)")
    r.add_argument("--steps", type=int)
    r.add_argument("--cfg", type=float)
    r.add_argument("--denoise", type=float)
    r.add_argument("--seed", type=int, default=-1)
    r.add_argument("--res", type=int, help="base resolution (e.g. 512, 768, 1024)")
    r.add_argument("--variants", type=int, default=1)
    r.add_argument("--layer-mask", choices=("auto", "soft", "selection", "none"), default="auto",
                   help="layer mask of the new layer: auto (default: none for Fill with a Fibo-type editor, else soft), "
                        "soft, hard from the selection, or none")
    r.add_argument("--no-fooocus", action="store_true", help="don't use the Fooocus patch (e.g. for SD1.5 models)")
    r.add_argument("--no-collage", action="store_true",
                   help="reference mode: do not paste a rough copy of the reference into the picture")
    r.add_argument("--no-enhance", action="store_true",
                   help="text-model workflows: send the prompt as typed, without the text model writing it")
    r.add_argument("--expand", type=int, nargs=4, default=[0, 0, 0, 0], metavar=("L", "T", "R", "B"),
                   help="outpaint: pixels to add on the left/top/right/bottom")
    a = ap.parse_args(argv)
    cfg = cfgmod.load(a.config)
    if a.cmd == "check":
        return cmd_check(cfg)
    if a.cmd == "windows":
        from . import winlink
        print(winlink.describe() if winlink.available() else "Only on Windows.")
        return 0
    if a.cmd == "probe":
        return cmd_probe(cfg)
    if a.cmd == "commands":
        return cmd_commands(cfg, a.pattern)
    if a.cmd == "run":
        return cmd_run(cfg, a)
    from .gui import run_gui
    return run_gui(cfg)


if __name__ == "__main__":
    sys.exit(main())
