"""Manual check (not part of run_all.py): Krea 2 / MOSS Expand, four ways against the visible seam (user 29.10.).

The first round (docs/tests/krea-moss-expand-ab.md) showed: with a description of the surroundings the content fits, but
the user rated 14 of 24 pictures bad, mostly for a visible edge or seam, a style that does not match and a brightness
jump. This round runs the plugin's Expand path directly in ComfyUI (no PhotoCraft) with the user's own pictures:

    A  as today: overlap 48 px onto the original
    B  wide: overlap 128 px (the soft edge is twice as wide)
    C  B + the seam correction (imaging.seam_correct)
    D  C + a second, weak run (denoise 0.4) over a band along the border only

Every picture gets the description of its surroundings first (Qwen 3.5 9B, bridge.SCENE_QUESTION), then two margins
(right 35 %; left and bottom 25 % each) x seeds x Krea 2 and MOSS. Then rate blind: the window shows the results in
random order without the variant; the summary reveals it.

    python tests\\live_expand_seam.py run --images <folder with pictures> [--seeds 1]
    python tests\\live_expand_seam.py rate          (the newest round; or give its folder)
    python tests\\live_expand_seam.py summary       (table per model and variant, also written to ergebnis.md)

Output: data\\expand-seam-test\\<time>\\ (pictures, key.json, bewertung.json, ergebnis.md). Needs ComfyUI with the Krea 2
and MOSS files and qwen3.5_9b_int8_convrot.safetensors; nothing in the plugin changes.
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
from PIL import Image, ImageDraw  # noqa: E402

from pccomfy import config as cfgmod, imaging, workflows  # noqa: E402
from pccomfy.bridge import SCENE_QUESTION, Bridge, Request  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "expand-seam-test"
MARGINS = {"right": (0, 0, 0.35, 0), "leftbottom": (0.25, 0, 0, 0.25)}     # left, top, right, bottom: share of the picture
MODELS = {"krea2": ("krea2-turbo-inpaint.json", 1024, 0.0), "moss": ("moss-image-inpaint.json", 1216, 0.5)}   # workflow, base res., match
VARIANTS = {"A": "as today (overlap 48)", "B": "wide (overlap 128)", "C": "wide + seam correction",
            "D": "wide + seam correction + weak second run on the border"}
OVERLAP = {"A": 48, "B": 128}
BAND = 96            # D: width of the band along the border (px on each side)
BAND_DENOISE = 0.4
MAX_SIDE = 1280      # pictures are scaled down to this (Expand works on a crop around the margin anyway)
REASONS = ["Fremdes im Rand", "Motiv doppelt", "Helligkeits-/Farbsprung an der Grenze", "Kante/Naht sichtbar",
           "Übergang verschmiert/unscharf", "Perspektive/Proportion falsch", "Stil passt nicht"]


class _NoPhotoCraft:
    pass


def canvas(im: Image.Image, margin: tuple) -> tuple[Image.Image, imaging.Box]:
    w, h = im.size
    l, t, r, b = (round(m * (w if k % 2 == 0 else h)) for k, m in enumerate(margin))
    c = Image.new("RGBA", (w + l + r, h + t + b), (255, 255, 255, 0))
    c.paste(im, (l, t))
    return c, imaging.Box(l, t, w, h)


def band_mask(keep: imaging.Box, size: tuple[int, int], width: int) -> Image.Image:
    """White along the border between the original and the new canvas (on the sides where canvas was added), `width` px
    to each side, soft at both ends."""
    W, H = size
    inner = imaging.outpaint_mask(keep, size, width)                  # new canvas + `width` px into the original
    x0 = keep.x - width if keep.x > 0 else 0
    y0 = keep.y - width if keep.y > 0 else 0
    x1 = keep.x + keep.w + width if keep.x + keep.w < W else W
    y1 = keep.y + keep.h + width if keep.y + keep.h < H else H
    outer = imaging.outpaint_mask(imaging.Box(x0, y0, x1 - x0, y1 - y0), size, width // 2)   # from `width` px into the margin on
    a = np.asarray(inner, dtype=np.int16) - np.asarray(outer, dtype=np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")


class Runner:
    def __init__(self, out: Path):
        self.b = Bridge(_NoPhotoCraft(), ComfyUI(cfgmod.load()["comfyui"]["url"]), out / "xch")
        self.out = out

    def expand(self, model, c, keep, mask, prompt, seed, denoise=1.0, seam=False):
        """One Expand run as the bridge does it (crop around the mask, model, colour match, scale back, layer mask)."""
        wf_name, base, match = MODELS[model]
        wf = str(ROOT / "workflows" / wf_name)
        W, H = c.size
        mult = workflows.size_multiple(workflows.load_template(wf))
        region = imaging.grow_box(imaging.mask_bbox(mask), (W, H), 0.4)
        gw, gh = imaging.gen_size(region.w, region.h, base, multiple=mult)
        src = imaging.clear_outside(c, keep) if denoise >= 1.0 else c
        crop = imaging.to_rgb(src.crop(region.pil())).resize((gw, gh), Image.LANCZOS)
        m = imaging.prepare_mask(mask.crop(region.pil()), 8, 8).resize((gw, gh), Image.BILINEAR)
        tag = f"{model}-{seed}-{time.time_ns() % 10**8}"
        iname = self.b.comfy.upload_image(crop, f"seam-{tag}-image.png")
        mname = self.b.comfy.upload_image(m.convert("RGB"), f"seam-{tag}-mask.png")
        req = Request(mode="outpaint", workflow=wf, enhance=False, base_res=base)
        p = workflows.GenParams(prompt=prompt, seed=seed, width=gw, height=gh, denoise=denoise)
        graph, out_node = self.b._graph(req, p, iname, mname, wf)
        hist = self.b._wait(self.b.comfy.queue(graph), graph, wf, 0, 1, "", lambda *a, **k: None)
        rgb = self.b.comfy.output_images(hist, out_node)[0].convert("RGB")
        small = mask.crop(region.pil()).resize(rgb.size, Image.BILINEAR)
        if match > 0:
            rgb = imaging.match_saturation(rgb, crop, small.point(lambda v: 255 if v > 127 else 0), match)
        if seam:
            rgb = imaging.seam_correct(rgb, crop, small)
        full = imaging.to_rgb(c).copy() if denoise < 1.0 else c.convert("RGB").copy()
        full.paste(rgb.resize((region.w, region.h), Image.LANCZOS), (region.x, region.y), mask.crop(region.pil()))
        return full


def cmd_run(a):
    files = sorted(f for f in Path(a.images).iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    if not files:
        sys.exit(f"No pictures in {a.images}")
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True)
    r = Runner(out)
    seeds = [11, 22, 33, 44][: max(1, a.seeds)]
    pics = {}
    for f in files:
        im = Image.open(f).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        t0 = time.time()
        pics[f.stem] = (im, r.b.describe_image(im, question=SCENE_QUESTION))
        print(f"described {f.name} ({time.time() - t0:.1f} s): {pics[f.stem][1]}", flush=True)
    key, n, t_start = {}, 0, time.time()
    total = len(pics) * len(MARGINS) * len(seeds) * len(MODELS)
    for model in MODELS:                 # one model after the other: each is loaded once
        for name, (im, prompt) in pics.items():
            for mg, margin in MARGINS.items():
                c, keep = canvas(im, margin)
                for seed in seeds:
                    n += 1
                    t0 = time.time()
                    res = {}
                    for v in ("A", "B"):
                        res[v] = r.expand(model, c, keep, imaging.outpaint_mask(keep, c.size, OVERLAP[v]), prompt, seed)
                    res["C"] = r.expand(model, c, keep, imaging.outpaint_mask(keep, c.size, OVERLAP["B"]), prompt, seed, seam=True)
                    band = band_mask(keep, c.size, BAND)
                    res["D"] = r.expand(model, res["C"].convert("RGBA"), keep, band, prompt, seed, denoise=BAND_DENOISE)
                    for v, full in res.items():
                        fid = f"{len(key) + 1:04d}"
                        full.save(out / "bilder" / f"{fid}.png")
                        key[fid] = {"bild": name, "rand": mg, "seed": seed, "modell": model, "variante": v,
                                    "keep": [keep.x, keep.y, keep.w, keep.h]}
                    print(f"{n}/{total} {model} {name} {mg} seed {seed}: {time.time() - t0:.0f} s", flush=True)
    order = list(key)
    random.Random(7).shuffle(order)
    json.dump({"order": order, "items": key, "prompts": {k: v[1] for k, v in pics.items()}, "variants": VARIANTS},
              open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {len(key)} pictures in {out}\n"
          f"Next: python tests\\live_expand_seam.py rate", flush=True)


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "key.json").exists()) if BASE.exists() else []
    if not runs:
        sys.exit(f"No test round in {BASE}")
    return runs[-1]


def cmd_rate(a):
    import tkinter as tk
    from PIL import ImageTk
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    order, items = key["order"], key["items"]
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title("Expand-Testrunde bewerten (blind)")
    root.configure(bg="#282828")
    st = {"i": next((k for k, fid in enumerate(order) if not data.get(fid, {}).get("bewertung")), 0), "loading": False}
    line, rating, note = tk.BooleanVar(value=False), tk.StringVar(), tk.StringVar()
    rvars = {r: tk.BooleanVar() for r in REASONS}
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"))
    top.pack(fill="x", pady=(8, 4))
    pic = tk.Label(root, bg="#282828")
    pic.pack(padx=8)
    side = tk.Frame(root, bg="#282828")
    side.pack(fill="x", padx=12, pady=8)
    rb = tk.Frame(side, bg="#282828")
    rb.pack(anchor="w")
    kw = dict(bg="#282828", activebackground="#282828", selectcolor="#535353")
    for k, label in (("1", "gut"), ("2", "mittel"), ("3", "schlecht")):
        tk.Radiobutton(rb, text=f"{label} ({k})", variable=rating, value=label, fg="#e6e6e6", font=("Segoe UI", 11),
                       command=lambda: save(), **kw).pack(side="left", padx=(0, 16))
    tk.Checkbutton(rb, text="Grenze zeigen (G)", variable=line, fg="#f28c28", command=lambda: show(), **kw).pack(side="left", padx=(24, 0))
    cb = tk.Frame(side, bg="#282828")
    cb.pack(anchor="w", pady=(6, 0))
    for k, r in enumerate(REASONS):
        tk.Checkbutton(cb, text=r, variable=rvars[r], fg="#cfcfcf", command=lambda: save(), **kw).grid(
            row=k // 4, column=k % 4, sticky="w", padx=(0, 14))
    nf = tk.Frame(side, bg="#282828")
    nf.pack(fill="x", pady=(6, 0))
    tk.Label(nf, text="Notiz:", bg="#282828", fg="#cfcfcf").pack(side="left")
    ent = tk.Entry(nf, textvariable=note, bg="#535353", fg="#ffffff", insertbackground="#ffffff", width=90)
    ent.pack(side="left", padx=6)
    nav = tk.Frame(side, bg="#282828")
    nav.pack(anchor="w", pady=(8, 0))
    tk.Button(nav, text="← Zurück", command=lambda: go(-1)).pack(side="left")
    tk.Button(nav, text="Weiter →", command=lambda: go(1)).pack(side="left", padx=8)
    status = tk.Label(nav, bg="#282828", fg="#9a9a9a")
    status.pack(side="left", padx=16)

    def count():
        status.configure(text=f"bewertet: {sum(1 for f in order if data.get(f, {}).get('bewertung'))}/{len(order)}  ·  "
                              f"gespeichert in {fout}")

    def show():
        fid = order[st["i"]]
        top.configure(text=f"Bild {st['i'] + 1}/{len(order)}")
        im = Image.open(out / "bilder" / f"{fid}.png").convert("RGB")
        if line.get():
            x, y, w, h = items[fid]["keep"]
            ImageDraw.Draw(im).rectangle((x, y, x + w, y + h), outline=(242, 140, 40), width=3)
        im.thumbnail((root.winfo_screenwidth() - 80, root.winfo_screenheight() - 300))
        st["photo"] = ImageTk.PhotoImage(im)
        pic.configure(image=st["photo"])
        st["loading"] = True
        rec = data.get(fid, {})
        rating.set(rec.get("bewertung", ""))
        for r, v in rvars.items():
            v.set(r in rec.get("gruende", []))
        note.set(rec.get("notiz", ""))
        st["loading"] = False
        count()

    def save():
        if st["loading"]:
            return
        data[order[st["i"]]] = {"bewertung": rating.get(), "gruende": [r for r, v in rvars.items() if v.get()],
                                "notiz": note.get().strip()}
        fout.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        count()

    def go(step):
        st["i"] = max(0, min(len(order) - 1, st["i"] + step))
        show()

    def key_press(e):
        if root.focus_get() is ent:
            return
        if e.char in ("1", "2", "3"):
            rating.set({"1": "gut", "2": "mittel", "3": "schlecht"}[e.char])
            save()
        elif e.keysym in ("Right", "Left"):
            go(1 if e.keysym == "Right" else -1)
        elif e.char in ("g", "G"):
            line.set(not line.get())
            show()

    note.trace_add("write", lambda *x: save())
    root.bind("<Key>", key_press)
    root.bind("<Button-1>", lambda e: root.focus_set() if e.widget is pic else None)
    root.state("zoomed")
    show()
    root.mainloop()


def cmd_summary(a):
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    lines = [f"# Expand-Testrunde {out.name}", "", f"Bewertet: {sum(1 for v in data.values() if v.get('bewertung'))} "
             f"von {len(key['items'])}", "", "| Modell | Variante | gut | mittel | schlecht | häufigste Gründe |", "|---|---|---|---|---|---|"]
    for model in MODELS:
        for v, text in VARIANTS.items():
            recs = [data[f] for f, it in key["items"].items() if it["modell"] == model and it["variante"] == v and f in data]
            c = {r: sum(1 for x in recs if x.get("bewertung") == r) for r in ("gut", "mittel", "schlecht")}
            reasons = {}
            for x in recs:
                for g in x.get("gruende", []):
                    reasons[g] = reasons.get(g, 0) + 1
            top = ", ".join(f"{g} ({k})" for g, k in sorted(reasons.items(), key=lambda t: -t[1])[:3])
            lines.append(f"| {'Krea 2' if model == 'krea2' else 'MOSS'} | {v}: {text} | {c['gut']} | {c['mittel']} | "
                         f"{c['schlecht']} | {top} |")
    notes = [(f, data[f]["notiz"]) for f in key["order"] if data.get(f, {}).get("notiz")]
    if notes:
        lines += ["", "Notizen:"] + [f"- {key['items'][f]['modell']} {key['items'][f]['variante']} "
                                     f"({key['items'][f]['bild']}, {key['items'][f]['rand']}): {n}" for f, n in notes]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--images", required=True, help="folder with your pictures (png, jpg, webp)")
    r.add_argument("--seeds", type=int, default=1, help="seeds per picture and margin (1 to 4)")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
