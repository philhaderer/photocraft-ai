"""Manual check (not part of run_all.py): MOSS Edit Canvas, which steps / CFG / skip-layer guidance (1.11.).

Six edit tasks on the user's own test pictures (C:\\programs\\testpics3\\resized_1280px), two seeds, six settings:
  S30   30 steps, CFG 4   (the LoRA author's values, the plugin's start)
  S15   15 steps, CFG 4   (the user found 15 enough)
  S10   10 steps, CFG 4
  C25   15 steps, CFG 2.5
  C55   15 steps, CFG 5.5
  NOSLG 15 steps, CFG 4, without skip-layer guidance

    python tests\\live_moss_edit.py run [--seeds 2] [--pics <folder>]
    python tests\\live_moss_edit.py blind [folder]    (pairs for: python tests\\live_moss_cfg.py rate <folder>)
    python tests\\live_moss_edit.py summary [folder]

Output: data\\moss-edit-test\\<time>\\ (pictures, contact sheet per task and seed with the source, timings.json). Needs ComfyUI
with the MOSS files and the edit LoRA; nothing in the plugin changes. Uses the GPU.
"""
import argparse
import json
import random
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw  # noqa: E402

from pccomfy import config as cfgmod, workflows  # noqa: E402
from pccomfy.bridge import Bridge, Request  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "moss-edit-test"
WF = ROOT / "workflows" / "moss-image-edit.json"
KEEP = "Keep everything else unchanged."
TASKS = [
    ("sweater", "IMG_20241224_145234.jpg", "Change only the blue patterned sweater to a plain green wool sweater. Keep the faces, the pose and the background unchanged."),
    ("winter", "IMG_20240921_102651.jpg", "Change only the season to winter with snow on the ground and on the rocks. Keep both people, their poses and the composition unchanged."),
    ("wall", "IMG_20241001_155006.jpg", "Change only the white wall to a light blue wall. Keep the girl, the ukuleles and the furniture unchanged."),
    ("sunset", "IMG_20241123_142913.jpg", "Change only the time of day to a warm sunset with long shadows. Keep the three people and the path unchanged."),
    ("background", "IMG_20240315_175437.jpg", "Change only the city in the background to a snowy mountain landscape. Keep the couple, their faces and their clothes unchanged."),
    ("remove", "IMG_20240918_191128.jpg", "Remove only the wine bottle from the table. " + KEEP),
]
SETTINGS = {  # key: (steps, cfg, slg)
    "S30": (30, 4.0, True), "S15": (15, 4.0, True), "S10": (10, 4.0, True),
    "C25": (15, 2.5, True), "C55": (15, 5.5, True), "NOSLG": (15, 4.0, False),
}
PAIRS = (("S15", "S30"), ("S10", "S30"), ("C25", "S15"), ("C55", "S15"), ("NOSLG", "S15"))


class _NoPhotoCraft:
    pass


def fit(im: Image.Image, px: int = 1024 * 1024) -> Image.Image:
    """About one megapixel, sides a multiple of 16 (the plugin's base resolution 1024 for MOSS Edit)."""
    s = (px / (im.width * im.height)) ** 0.5
    return im.resize((max(16, round(im.width * s / 16) * 16), max(16, round(im.height * s / 16) * 16)), Image.LANCZOS)


def cmd_run(a):
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True)
    b = Bridge(_NoPhotoCraft(), ComfyUI(url), out / "xch")
    seeds = [101, 202, 303][: max(1, a.seeds)]
    times, n, total, t_start = {}, 0, len(TASKS) * len(seeds) * len(SETTINGS), time.time()
    for name, pic, prompt in TASKS:
        src = fit(Image.open(Path(a.pics) / pic).convert("RGB"))
        up = b.comfy.upload_image(src, f"pcc-edittest-{name}.png")
        for seed in seeds:
            ims = []
            for key, (steps, cfg, slg) in SETTINGS.items():
                n += 1
                t0 = time.time()
                req = Request(mode="edit", workflow=str(WF), enhance=False, sampler_override={"steps": steps, "cfg": cfg})
                p = workflows.GenParams(prompt=prompt, seed=seed, width=src.width, height=src.height)
                graph, out_node = b._graph(req, p, up, None, str(WF))
                if not slg:       # the skip-layer guidance node (3) drops out: the sampler reads the model of the edit LoRA
                    graph["40"]["inputs"]["model"] = ["2", 0]
                    graph.pop("3", None)
                pid = b.comfy.queue(graph)
                hist = b._wait(pid, graph, str(WF), 0, 1, "", lambda *x, **k: None)
                for _ in range(10):       # the history may lag a moment behind the "finished" message
                    if hist.get("outputs"):
                        break
                    time.sleep(1.5)
                    hist = b.comfy.history(pid) or {}
                im = b.comfy.output_images(hist, out_node)[0].convert("RGB")
                dt = time.time() - t0
                im.save(out / "bilder" / f"{name}-s{seed}-{key}.png")
                times[f"{name}-s{seed}-{key}"] = round(dt, 1)
                ims.append((key, im))
                print(f"{n}/{total} {name} seed {seed} {key}: {dt:.0f} s", flush=True)
            tw = 420
            th = int(src.height * tw / src.width)
            sheet = Image.new("RGB", (tw * 4 + 50, (th + 22) * 2 + 8), (40, 40, 40))
            d = ImageDraw.Draw(sheet)
            for i, (key, im) in enumerate([("source", src)] + ims):
                x, y = 10 + (i % 4) * (tw + 10), 4 + (i // 4) * (th + 22)
                d.text((x, y), key if key == "source" else f"{key} {SETTINGS[key]}", fill=(230, 230, 230))
                sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 16))
            sheet.save(out / f"blatt-{name}-s{seed}.jpg", quality=88)
    json.dump(times, open(out / "timings.json", "w"), indent=1)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {out}", flush=True)


def latest(folder):
    if folder:
        return Path(folder)
    return sorted(p for p in BASE.iterdir() if (p / "bilder").exists())[-1]


def cmd_blind(folder):
    out = latest(folder)
    if (out / "bilder_original").exists():
        sys.exit("blind pairs exist already")
    sets = {}
    for f in sorted((out / "bilder").glob("*.png")):
        base, key = f.stem.rsplit("-", 1)
        sets.setdefault(base, {})[key] = f
    sets = {b: v for b, v in sets.items() if set(v) >= set(SETTINGS)}
    (out / "blind").mkdir(exist_ok=True)
    names = [t[0] for t in TASKS]
    items, pairs, n = {}, [], 0
    for base, v in sets.items():
        task = base.rsplit("-s", 1)[0]
        for x, y in PAIRS:
            ids = []
            for k in (x, y):
                n += 1
                fid = f"{n:04d}"
                shutil.copy(v[k], out / "blind" / f"{fid}.png")
                items[fid] = {"prompt_nr": names.index(task) + 1, "variant": k, "set": base}
                ids.append(fid)
            pairs.append(ids)
    rnd = random.Random(5)
    rnd.shuffle(pairs)
    for pr in pairs:
        rnd.shuffle(pr)
    (out / "bilder").rename(out / "bilder_original")
    (out / "blind").rename(out / "bilder")
    json.dump({"pairs": pairs, "items": items, "prompts": {str(i + 1): t[2] for i, t in enumerate(TASKS)}, "size": "",
               "title": "MOSS Edit Canvas: Paare blind vergleichen"}, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(pairs)} pairs from {len(sets)} sets in {out}")
    print("Rate: python tests/live_moss_cfg.py rate", out)


def cmd_summary(folder):
    out = latest(folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    items, tally = key["items"], {}
    for rec in data.values():
        w = rec.get("wahl")
        if not w:
            continue
        a, b = items[rec["links"]]["variant"], items[rec["rechts"]]["variant"]
        t = tally.setdefault((a, b) if (a, b) in PAIRS else (b, a), {a: 0, b: 0, "gleich": 0, "beide schlecht": 0})
        if w in ("links", "rechts"):
            t[items[rec[w]]["variant"]] += 1
        else:
            t[w] += 1
    lines = ["# MOSS Edit Canvas, blind", ""]
    for (a, b), t in tally.items():
        lines.append(f"- {a} {SETTINGS[a]} gegen {b} {SETTINGS[b]}: {t[a]} : {t[b]}, gleich {t['gleich']}, beide schlecht {t['beide schlecht']}")
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--seeds", type=int, default=2)
    r.add_argument("--pics", default=r"C:\programs\testpics3\resized_1280px")
    for name in ("blind", "summary"):
        sub.add_parser(name).add_argument("folder", nargs="?")
    a = ap.parse_args()
    {"run": cmd_run, "blind": lambda x: cmd_blind(x.folder), "summary": lambda x: cmd_summary(x.folder)}[a.cmd](a)


if __name__ == "__main__":
    main()
