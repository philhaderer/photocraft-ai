"""Manual check (not part of run_all.py): the Fill mask test round, stage 2 (user 30.10.; stage 1 is
tests/test_fill_mask_variants.py).

Qwen and Fibo Fill redraw the whole crop around the selection; the layer mask decides how much of it shows. The narrow
soft edge of today cut off the fill's edge and its shadow (28.10.), today's 5 % density shows almost the whole crop. This
round runs the plugin's Fill path directly in ComfyUI (no PhotoCraft) once per case and lays the four masks of
pccomfy/fillmask.py over the same result:

    narrow     today: narrow soft edge outside the selection
    density5   today's start value: the same mask at 5 % density
    crop_fade  fades out to the crop's sides (the attempt of 28.10., checked at the canvas edges)
    wide       a soft edge three times as wide

Cases (cut to a quarter, user 30.10.): 4 pictures x 5 positions (a free spot in the middle; left edge, top edge, top-left
and bottom-right corner, each touching the canvas edge) x Fibo and Qwen = 40 runs, one seed, Context 0.4; rectangle and
hard lasso take turns, so every picture and position gets both; every model with its Fill start values
(Edge feather, base resolution; Fibo with its seam correction). Measured for every picture: the jump at the crop's sides
inside the picture, and how much of what the model changed outside the selection stays visible. Then rate blind: 40
cases (each picture, position and model once), the four variants side by side in random order; pick the best and tick
what is wrong.

    python tests\\live_fill_mask.py run --images A:\\testpics3\\resized_1280px
    python tests\\live_fill_mask.py rate          (the newest round; or give its folder)
    python tests\\live_fill_mask.py summary       (tables, also written to ergebnis.md)

Output: data\\fill-mask-test\\<time>\\ (results, pictures per variant, key.json, bewertung.json, ergebnis.md). Needs
ComfyUI with the Fibo and Qwen files; nothing in the plugin changes.
"""
import argparse
import json
import random
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from pccomfy import config as cfgmod, fillmask, imaging, models, workflows  # noqa: E402
from pccomfy.bridge import Bridge, Request, fill_prompt, outline_width, prompt_phase_nodes  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "fill-mask-test"
PICTURES = ["IMG_20240522_194039_1", "IMG_20240921_102651", "IMG_20241001_155006", "IMG_20241123_142913"]
#             room with a piano frame, gorge in the woods, wall with ukuleles, path outdoors (A:\testpics3\resized_1280px)
POSITIONS = ["middle", "left", "top", "top-left", "bottom-right"]
SEL_W, SEL_H = 0.26, 0.32                          # selection size: share of the picture's width and height
# "middle" is a free spot per picture (top-left corner of the selection, share of the picture); the others touch the edge
MIDDLE = {"IMG_20240522_194039_1": (0.55, 0.62), "IMG_20240921_102651": (0.30, 0.05),
          "IMG_20241001_155006": (0.24, 0.05), "IMG_20241123_142913": (0.33, 0.45)}
# what to fill: per picture and position (objects that stand on something cast a shadow; the round is about the edge)
OBJECTS = {
    "IMG_20240522_194039_1": {"middle": "a wooden stool standing on the floor", "left": "a tall potted plant",
                              "top": "a framed picture hanging on the wall", "top-left": "a round wall clock",
                              "bottom-right": "a cardboard box on the floor"},
    "IMG_20240921_102651": {"middle": "a large mossy boulder", "left": "a fallen tree trunk",
                            "top": "a small wooden hut", "top-left": "a wooden signpost",
                            "bottom-right": "a hiking backpack on the ground"},
    "IMG_20241001_155006": {"middle": "a framed landscape painting on the wall", "left": "a tall floor lamp",
                            "top": "a round wall clock", "top-left": "a wall shelf with books",
                            "bottom-right": "a potted plant on the floor"},
    "IMG_20241123_142913": {"middle": "a park bench beside the path", "left": "a red mailbox on a post",
                            "top": "a hot air balloon", "top-left": "a red kite in the sky",
                            "bottom-right": "a dog sitting on the grass"},
}
MODELS = ["fibo", "qwen"]
SHAPES = ["rect", "lasso"]
CONTEXT = 0.4                                      # the Fill start value (user 30.10.: the round cut to a quarter)
SEED = 11
MAX_SIDE = 1280
ISSUES = ["Schatten/Rand der Füllung abgeschnitten", "Gerade Kante des Ausschnitts sichtbar",
          "Farb-/Helligkeitsfleck um die Auswahl", "Füllung am Bildrand weich"]


def box_at(size, pos, name=""):
    W, H = size
    w, h = round(W * SEL_W), round(H * SEL_H)
    if pos == "middle" and name in MIDDLE:
        return round(W * MIDDLE[name][0]), round(H * MIDDLE[name][1]), w, h
    x = {"middle": (W - w) // 2, "left": 0, "top": (W - w) // 2, "top-left": 0, "bottom-right": W - w}[pos]
    y = {"middle": (H - h) // 2, "left": (H - h) // 2, "top": 0, "top-left": 0, "bottom-right": H - h}[pos]
    return x, y, w, h


def selection(size, pos, shape, name=""):
    """The selection as PhotoCraft exports it: white = selected, hard edge (a lasso without smoothing)."""
    x, y, w, h = box_at(size, pos, name)
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    if shape == "rect":
        d.rectangle((x, y, x + w - 1, y + h - 1), fill=255)
    else:
        cx, cy = x + w / 2, y + h / 2
        pts = [(cx + w / 2 * (0.85 + 0.15 * np.sin(3 * t)) * np.cos(t), cy + h / 2 * (0.85 + 0.15 * np.cos(2 * t)) * np.sin(t))
               for t in np.linspace(0, 2 * np.pi, 48, endpoint=False)]
        d.polygon([(min(size[0] - 1, max(0, px)), min(size[1] - 1, max(0, py))) for px, py in pts], fill=255)
    return m


class _NoPhotoCraft:
    pass


class Runner:
    def __init__(self, out: Path):
        self.b = Bridge(_NoPhotoCraft(), ComfyUI(cfgmod.load()["comfyui"]["url"]), out / "xch")

    def fill(self, model, im, mask, prompt, ctx):
        """One Fill run as the bridge does it with an editor: crop around the selection, red outline, the fixed wrapper
        around the text, the model, Fibo's seam correction. Returns the result (the size of the crop), region and bbox."""
        mdl = models.BY_KEY[model]
        spec = mdl.modes["inpaint"]
        st = spec.settings
        wf = str(ROOT / "workflows" / spec.workflow)
        tpl = workflows.load_template(wf)
        W, H = im.size
        bbox = imaging.mask_bbox(mask)
        region = imaging.grow_box(bbox, (W, H), ctx)
        gw, gh = imaging.gen_size(region.w, region.h, st.get("base_res", 1024), multiple=workflows.size_multiple(tpl))
        crop = imaging.to_rgb(im.crop(region.pil())).resize((gw, gh), Image.LANCZOS)
        sel = mask.crop(region.pil())
        marked = imaging.mark_outline(crop, sel.resize((gw, gh), Image.NEAREST), outline_width(gw, gh))
        tag = f"{model}-{time.time_ns() % 10**9}"
        iname = self.b.comfy.upload_image(marked, f"fillmask-{tag}-image.png")
        mname = None
        if workflows.has_tag(tpl, "mask"):
            m = imaging.prepare_mask(sel, st.get("mask_grow", 8), st.get("mask_blur", 8)).resize((gw, gh), Image.BILINEAR)
            mname = self.b.comfy.upload_image(m.convert("RGB"), f"fillmask-{tag}-mask.png")
        req = Request(mode="inpaint", workflow=wf, enhance=st.get("enhance", True), turbo=st.get("turbo", True),
                      base_res=st.get("base_res", 1024), context=ctx)
        p = workflows.GenParams(prompt=fill_prompt(prompt, sel, wf), seed=SEED, width=gw, height=gh)
        graph, out_node = self.b._graph(req, p, iname, mname, wf, force_plain=not (req.enhance and prompt_phase_nodes(tpl)))
        hist = self.b._wait(self.b.comfy.queue(graph), graph, wf, 0, 1, "", lambda *a, **k: None)
        rgb = self.b.comfy.output_images(hist, out_node)[0].convert("RGB")
        if mdl.seam == "on":
            rgb = imaging.seam_correct(rgb, crop, sel.resize(rgb.size, Image.BILINEAR))
        return rgb, region, bbox, st.get("feather_pct", 2.0)


def measure(original, result, region, sel, eff):
    """jump: mean step in levels where the crop's sides lie inside the picture (the composite's last row inside against
    the original's first row outside, minus the same step in the original). kept: share of what the model changed outside
    the selection (in the crop) that stays visible."""
    W, H = original.size
    o = np.asarray(original.convert("L"), dtype=np.float32)
    c = o.copy()
    r = np.asarray(result.convert("L").resize((region.w, region.h), Image.LANCZOS), dtype=np.float32)
    e = np.asarray(eff, dtype=np.float32) / 255.0
    x0, y0, x1, y1 = region.x, region.y, region.x + region.w, region.y + region.h
    c[y0:y1, x0:x1] = e * r + (1 - e) * o[y0:y1, x0:x1]
    steps = []
    if x0 > 0:
        steps.append(np.abs(c[y0:y1, x0] - o[y0:y1, x0 - 1]).mean() - np.abs(o[y0:y1, x0] - o[y0:y1, x0 - 1]).mean())
    if y0 > 0:
        steps.append(np.abs(c[y0, x0:x1] - o[y0 - 1, x0:x1]).mean() - np.abs(o[y0, x0:x1] - o[y0 - 1, x0:x1]).mean())
    if x1 < W:
        steps.append(np.abs(c[y0:y1, x1 - 1] - o[y0:y1, x1]).mean() - np.abs(o[y0:y1, x1 - 1] - o[y0:y1, x1]).mean())
    if y1 < H:
        steps.append(np.abs(c[y1 - 1, x0:x1] - o[y1, x0:x1]).mean() - np.abs(o[y1 - 1, x0:x1] - o[y1, x0:x1]).mean())
    out = np.asarray(sel, dtype=np.uint8) <= 127
    diff = np.abs(r - o[y0:y1, x0:x1]) * out
    kept = float((diff * e).sum() / max(diff.sum(), 1e-6))
    return {"jump": round(float(np.mean(steps)) if steps else 0.0, 2), "kept": round(kept, 3)}


def cmd_run(a):
    folder = Path(a.images)
    files = {f.stem: f for f in folder.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")}
    missing = [n for n in PICTURES if n not in files]
    if missing:
        sys.exit(f"Missing in {folder}: {', '.join(missing)}")
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    for d in ("ergebnisse", "bilder"):
        (out / d).mkdir(parents=True)
    r = Runner(out)
    pics = {}
    for n in PICTURES:
        im = Image.open(files[n]).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        pics[n] = im
    cases, n_done, t_start = {}, 0, time.time()
    total = len(MODELS) * len(PICTURES) * len(POSITIONS)
    for model in MODELS:                 # one model after the other: each is loaded once
        for i, (name, im) in enumerate(pics.items()):
            for j, pos in enumerate(POSITIONS):
                shape = SHAPES[(i + j) % 2]      # rectangle and lasso take turns: every picture and position gets both
                ctx = CONTEXT
                mask = selection(im.size, pos, shape, name)
                n_done += 1
                t0 = time.time()
                cid = f"{len(cases) + 1:03d}"
                rgb, region, bbox, pct = r.fill(model, im, mask, OBJECTS[name][pos], ctx)
                rgb.save(out / "ergebnisse" / f"{cid}.png")
                sel = mask.crop(region.pil())
                variants = {}
                for v in fillmask.VARIANTS:
                    m, dens = fillmask.layer_mask(v, mask, region, bbox, pct)
                    fillmask.composite(im, rgb, region, m, dens).save(out / "bilder" / f"{cid}-{v}.png")
                    variants[v] = measure(im, rgb, region, sel, fillmask.effective(m, dens))
                cases[cid] = {"bild": name, "position": pos, "form": shape, "context": ctx, "modell": model,
                              "prompt": OBJECTS[name][pos], "feather_pct": pct,
                              "region": [region.x, region.y, region.w, region.h], "messung": variants}
                print(f"{n_done}/{total} {model} {name[:22]} {pos} {shape}: {time.time() - t0:.0f} s", flush=True)
    rate = list(cases)                    # the blind part: every case
    rng = random.Random(7)
    rng.shuffle(rate)
    shown = {cid: rng.sample(list(fillmask.VARIANTS), len(fillmask.VARIANTS)) for cid in rate}
    json.dump({"cases": cases, "rate": rate, "shown": shown, "variants": fillmask.VARIANTS, "issues": ISSUES},
              open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {len(cases)} cases, {len(rate)} to rate, in {out}\n"
          f"Next: python tests\\live_fill_mask.py rate", flush=True)


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "key.json").exists()) if BASE.exists() else []
    if not runs:
        sys.exit(f"No test round in {BASE}")
    return runs[-1]


def view_box(region, size, grow=0.25):
    """The part of the picture to show: the crop and a quarter of its size around it (so its sides are visible)."""
    x, y, w, h = region
    W, H = size
    dx, dy = round(w * grow), round(h * grow)
    return max(0, x - dx), max(0, y - dy), min(W, x + w + dx), min(H, y + h + dy)


def cmd_rate(a):
    import tkinter as tk
    from PIL import ImageTk
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    cases, order, shown = key["cases"], key["rate"], key["shown"]
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title("Fill-Masken-Testrunde bewerten (blind)")
    root.configure(bg="#282828")
    st = {"i": next((k for k, c in enumerate(order) if not data.get(c, {}).get("bestes")), 0), "loading": False, "whole": False, "outline": False}
    best, note = tk.StringVar(), tk.StringVar()
    ivars = [{s: tk.BooleanVar() for s in ISSUES} for _ in range(4)]
    kw = dict(bg="#282828", activebackground="#282828", selectcolor="#535353")
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"))
    top.pack(fill="x", pady=(6, 2))
    grid = tk.Frame(root, bg="#282828")
    grid.pack()
    tiles = []
    for k in range(4):
        f = tk.Frame(grid, bg="#282828")
        f.grid(row=k // 2, column=k % 2, padx=6, pady=4, sticky="n")
        lbl = tk.Label(f, bg="#282828")
        lbl.pack()
        row = tk.Frame(f, bg="#282828")         # "best" on the left, the four issues in two rows beside it
        row.pack(anchor="w")
        tk.Radiobutton(row, text=f"Bestes ({k + 1})", variable=best, value=str(k + 1), fg="#f28c28",
                       command=lambda: save(), **kw).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))
        for j, s in enumerate(ISSUES):
            tk.Checkbutton(row, text=s, variable=ivars[k][s], fg="#cfcfcf", font=("Segoe UI", 8),
                           command=lambda: save(), **kw).grid(row=j // 2, column=1 + j % 2, sticky="w")
        tiles.append(lbl)
    bar = tk.Frame(root, bg="#282828")
    bar.pack(fill="x", padx=12, pady=4)
    tk.Label(bar, text="Notiz:", bg="#282828", fg="#cfcfcf").pack(side="left")
    ent = tk.Entry(bar, textvariable=note, bg="#535353", fg="#ffffff", insertbackground="#ffffff", width=60)
    ent.pack(side="left", padx=6)
    tk.Button(bar, text="← Zurück", command=lambda: go(-1)).pack(side="left", padx=(12, 0))
    tk.Button(bar, text="Weiter →", command=lambda: go(1)).pack(side="left", padx=8)
    tk.Button(bar, text="Ganzes Bild (V)", command=lambda: whole()).pack(side="left")
    tk.Button(bar, text="Auswahl zeigen (O)", command=lambda: outline()).pack(side="left", padx=(8, 0))
    status = tk.Label(bar, bg="#282828", fg="#9a9a9a")
    status.pack(side="left", padx=12)

    def count():
        status.configure(text=f"bewertet: {sum(1 for c in order if data.get(c, {}).get('bestes'))}/{len(order)}")

    def show():
        cid = order[st["i"]]
        c = cases[cid]
        top.configure(text=f"Fall {st['i'] + 1}/{len(order)}")
        sw, sh = root.winfo_screenwidth() // 2 - 40, (root.winfo_screenheight() - 160) // 2 - 70   # room for the ticks
        st["photos"] = []
        for k, v in enumerate(shown[cid]):
            im = Image.open(out / "bilder" / f"{cid}-{v}.png").convert("RGB")
            if st["outline"]:          # the selection as an orange line (the same one the run used)
                edge = selection(im.size, c["position"], c["form"], c["bild"]).filter(ImageFilter.FIND_EDGES)
                im.paste((242, 140, 40), (0, 0), edge.point(lambda x: 255 if x else 0).filter(ImageFilter.MaxFilter(3)))
            if not st["whole"]:
                im = im.crop(view_box(c["region"], im.size))
            im.thumbnail((sw, sh))
            ph = ImageTk.PhotoImage(im)
            st["photos"].append(ph)
            tiles[k].configure(image=ph)
        st["loading"] = True
        rec = data.get(cid, {})
        best.set(rec.get("bestes", ""))
        for k, v in enumerate(shown[cid]):
            for s, var in ivars[k].items():
                var.set(s in rec.get("probleme", {}).get(v, []))
        note.set(rec.get("notiz", ""))
        st["loading"] = False
        count()

    def save():
        if st["loading"]:
            return
        cid = order[st["i"]]
        vs = shown[cid]
        data[cid] = {"bestes": best.get(), "bestes_variante": vs[int(best.get()) - 1] if best.get() else "",
                     "probleme": {v: [s for s, var in ivars[k].items() if var.get()] for k, v in enumerate(vs)},
                     "notiz": note.get().strip()}
        fout.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        count()

    def go(step):
        st["i"] = max(0, min(len(order) - 1, st["i"] + step))
        show()

    def whole():
        st["whole"] = not st["whole"]
        show()

    def outline():
        st["outline"] = not st["outline"]
        show()

    def key_press(e):
        if root.focus_get() is ent:
            return
        if e.char in ("1", "2", "3", "4"):
            best.set(e.char)
            save()
        elif e.keysym in ("Right", "Left"):
            go(1 if e.keysym == "Right" else -1)
        elif e.char in ("v", "V"):
            whole()
        elif e.char in ("o", "O"):
            outline()

    note.trace_add("write", lambda *x: save())
    root.bind("<Key>", key_press)
    root.state("zoomed")
    show()
    root.mainloop()


def cmd_summary(a):
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    cases, variants = key["cases"], key["variants"]
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    lines = [f"# Fill-Masken-Testrunde {out.name}", "", f"{len(cases)} Fälle; blind bewertet: "
             f"{sum(1 for v in data.values() if v.get('bestes'))} von {len(key['rate'])}", "",
             "## Messung (alle Fälle)", "", "Sprung = Stufe an den Seiten des Ausschnitts (Graustufen, 0 = unsichtbar); "
             "behalten = Anteil der Änderungen außerhalb der Auswahl, der sichtbar bleibt (Schatten, Rand der Füllung).", "",
             "| Modell | Variante | Sprung (Mittel) | Sprung (schlimmster) | behalten |", "|---|---|---|---|---|"]
    for model in MODELS:
        for v, text in variants.items():
            ms = [c["messung"][v] for c in cases.values() if c["modell"] == model]
            if ms:
                lines.append(f"| {model} | {text} | {np.mean([m['jump'] for m in ms]):.1f} | {max(m['jump'] for m in ms):.1f} | "
                             f"{100 * np.mean([m['kept'] for m in ms]):.0f} % |")
    lines += ["", "## Blindbewertung", "", "| Modell | Variante | bestes | " + " | ".join(ISSUES) + " |",
              "|---|---|---|" + "---|" * len(ISSUES)]
    for model in MODELS:
        recs = [(cid, r) for cid, r in data.items() if cases[cid]["modell"] == model]
        for v, text in variants.items():
            wins = sum(1 for _, r in recs if r.get("bestes_variante") == v)
            iss = [sum(1 for _, r in recs if s in r.get("probleme", {}).get(v, [])) for s in ISSUES]
            lines.append(f"| {model} | {text} | {wins} | " + " | ".join(str(i) for i in iss) + " |")
    by_pos = {}
    for cid, r in data.items():
        if r.get("bestes_variante"):
            p = cases[cid]["position"]
            by_pos.setdefault(p, {}).setdefault(r["bestes_variante"], 0)
            by_pos[p][r["bestes_variante"]] += 1
    if by_pos:
        lines += ["", "Bestes je Position: " + "; ".join(f"{p}: " + ", ".join(f"{v} {n}" for v, n in sorted(d.items(), key=lambda t: -t[1]))
                                                       for p, d in by_pos.items())]
    notes = [(cid, r["notiz"]) for cid, r in data.items() if r.get("notiz")]
    if notes:
        lines += ["", "Notizen:"] + [f"- {cases[c]['modell']} {cases[c]['bild']} {cases[c]['position']}: {n}" for c, n in notes]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--images", required=True, help="the folder with the test pictures (A:\\testpics3\\resized_1280px)")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
