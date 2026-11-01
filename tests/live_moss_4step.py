"""Manual check (not part of run_all.py): MOSS Text to image with the 4-step Turbo LoRA on ten stock-photography motives.

Four variants per motive and seed, everything else as the plugin's start settings (no LLM, SLG off):
  A  4-step Turbo LoRA, 4 steps, CFG 1, euler / simple, without the UltraReal LoRA
  B  4-step Turbo LoRA, as A with the UltraReal LoRA
  C  the plugin's start: 35 steps, CFG 3.0, UltraReal on, no speed LoRA
  D  DMD2: 8 steps, CFG 1.5, UltraReal on

    python tests\\live_moss_4step.py [--seeds 2] [--size 1344x896]

Output: data\\moss-4step-test\\<time>\\ (single pictures, one contact sheet per motive and seed with the variant under each
picture, timings.json). Needs ComfyUI with the MOSS files and both LoRAs; nothing in the plugin changes. Uses the GPU.
"""
import argparse
import json
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

BASE = cfgmod.CONFIG_DIR / "moss-4step-test"
WF = ROOT / "workflows" / "moss-image-t2i.json"
SLG, LENOVO = "7", "5"        # stage ids of moss-image-t2i.json (order in the window: 4-step LoRA = stage_on, UltraReal, SLG)

MOTIVES = [
    ("team-meeting", "A diverse team of four colleagues around a glass meeting table in a bright modern office, laptops and coffee cups, "
                     "one woman pointing at a screen, candid smiles, natural daylight from large windows, shallow depth of field"),
    ("summer-salad", "Overhead shot of a rustic wooden table with a bowl of fresh summer salad, cherry tomatoes, mozzarella, basil leaves, "
                     "an olive oil bottle and a linen napkin, soft window light, natural colours"),
    ("hiker-sunrise", "A lone hiker with a red backpack standing on a mountain ridge at sunrise, mist in the valleys below, warm golden light, "
                      "wide angle photograph, seen from behind"),
    ("baking-family", "A mother and her young daughter baking cookies in a sunny kitchen, flour on their hands, laughing, "
                      "warm natural light, authentic family moment"),
    ("coffee-mug", "A white ceramic coffee mug with steam on a clean light grey seamless background, soft studio lighting, "
                   "subtle shadow, plenty of empty space on the left for text"),
    ("doctor-patient", "A friendly female doctor in a white coat talking with an elderly patient in a bright clinic room, "
                       "stethoscope around her neck, empathetic expression, natural light"),
    ("cafe-remote-work", "A young man working on a laptop at a small cafe table by a window, cappuccino, a plant, "
                         "rain on the street outside, cosy atmosphere, candid"),
    ("alpine-lake", "A calm turquoise alpine lake surrounded by pine forest and snow-capped peaks at midday, clear reflections, "
                    "a small wooden jetty in the foreground"),
    ("glass-tower", "A modern glass office tower seen from below against a blue sky with a few white clouds, strong converging lines, "
                    "clean and symmetrical architecture photograph"),
    ("lakeside-jogger", "A woman in her thirties jogging along a lakeside path early in the morning, soft backlight, fitness watch, "
                        "dew on the grass, hair moving, fresh and energetic"),
]

# name, label, request fields, sampler override
VARIANTS = [
    ("A", "A 4-step", dict(turbo=False, stage_on=True, stages_off=[LENOVO, SLG]), {"steps": 4, "cfg": 1.0, "sampler": "euler", "scheduler": "simple"}),
    ("B", "B 4-step + UltraReal", dict(turbo=False, stage_on=True, stages_off=[SLG]), {"steps": 4, "cfg": 1.0, "sampler": "euler", "scheduler": "simple"}),
    ("C", "C 35 steps (start)", dict(turbo=False, stage_on=False, stages_off=[SLG]), {}),
    ("D", "D DMD2 8 steps", dict(turbo=True, stage_on=False, stages_off=[SLG]), {}),
]


class _NoPhotoCraft:
    pass


PAIRS = (("B", "C"), ("B", "D"), ("A", "B"))      # 4-step + UltraReal against the start and DMD2; the effect of UltraReal on 4-step
NAMES = {k: label for k, label, _f, _o in VARIANTS}


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "bilder").exists() and any((p / "bilder").iterdir()))
    return runs[-1]


def cmd_blind(folder):
    import random
    import shutil
    out = latest(folder)
    sets = {}
    for f in sorted((out / "bilder").glob("*.png")):
        stem = f.stem
        if not stem.count("-s"):
            continue
        base, key = stem.rsplit("-", 1)
        sets.setdefault(base, {})[key] = f
    sets = {b: v for b, v in sets.items() if set(v) >= set("ABCD")}      # only finished sets
    (out / "blind").mkdir(exist_ok=True)
    names = [m for m, _ in MOTIVES]
    items, pairs, n = {}, [], 0
    for base, v in sets.items():
        motive = base.rsplit("-s", 1)[0]
        for a, b in PAIRS:
            ids = []
            for k in (a, b):
                n += 1
                fid = f"{n:04d}"
                shutil.copy(v[k], out / "blind" / f"{fid}.png")
                items[fid] = {"prompt_nr": names.index(motive) + 1, "variant": k, "set": base}
                ids.append(fid)
            pairs.append(ids)
    rnd = random.Random(11)
    rnd.shuffle(pairs)
    for pr in pairs:
        rnd.shuffle(pr)
    prompts = {str(i + 1): t for i, (_m, t) in enumerate(MOTIVES)}
    # live_moss_cfg.py reads the pictures from "bilder": the blind copies go there under their blind ids
    (out / "bilder_original").exists() or (out / "bilder").rename(out / "bilder_original")
    (out / "blind").rename(out / "bilder")
    json.dump({"pairs": pairs, "items": items, "prompts": prompts, "size": "", "title": "MOSS 4-step: Paare blind vergleichen"},
              open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(pairs)} pairs from {len(sets)} sets in {out}")
    print("Rate: python tests/live_moss_cfg.py rate", out)


def cmd_summary(folder):
    out = latest(folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    data = json.loads((out / "bewertung.json").read_text(encoding="utf-8")) if (out / "bewertung.json").exists() else {}
    items, tally = key["items"], {}
    for rec in data.values():
        w = rec.get("wahl")
        if not w:
            continue
        a, b = items[rec["links"]]["variant"], items[rec["rechts"]]["variant"]
        t = tally.setdefault(tuple(sorted((a, b))), {a: 0, b: 0, "gleich": 0, "beide schlecht": 0})
        if w in ("links", "rechts"):
            t[items[rec[w]]["variant"]] += 1
        else:
            t[w] += 1
    lines = ["# MOSS 4-step, blind", ""]
    for (a, b), t in sorted(tally.items()):
        lines.append(f"- {NAMES[a]} gegen {NAMES[b]}: {t[a]} : {t[b]}, gleich {t['gleich']}, beide schlecht {t['beide schlecht']}")
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("blind", "summary"):
        {"blind": cmd_blind, "summary": cmd_summary}[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else None)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        del sys.argv[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--size", default="1344x896")
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.lower().split("x"))
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True)
    b = Bridge(_NoPhotoCraft(), ComfyUI(url), out / "xch")
    seeds = [101, 202, 303, 404][: max(1, a.seeds)]
    times, n, total, t_start = {}, 0, len(MOTIVES) * len(seeds) * len(VARIANTS), time.time()
    for name, prompt in MOTIVES:
        for seed in seeds:
            sheet_ims = []
            for key, label, fields, override in VARIANTS:
                n += 1
                t0 = time.time()
                req = Request(mode="txt2img", workflow=str(WF), enhance=False, sampler_override=override, **fields)
                p = workflows.GenParams(prompt=prompt, seed=seed, width=w, height=h)
                graph, out_node = b._graph(req, p, None, None, str(WF))
                hist = b._wait(b.comfy.queue(graph), graph, str(WF), 0, 1, "", lambda *x, **k: None)
                im = b.comfy.output_images(hist, out_node)[0].convert("RGB")
                dt = time.time() - t0
                im.save(out / "bilder" / f"{name}-s{seed}-{key}.png")
                times[f"{name}-s{seed}-{key}"] = round(dt, 1)
                sheet_ims.append((label, im))
                print(f"{n}/{total} {name} seed {seed} {label}: {dt:.0f} s", flush=True)
            tw = 640
            th = int(h * tw / w)
            sheet = Image.new("RGB", (tw * 2 + 30, (th + 28) * 2 + 10), (40, 40, 40))
            d = ImageDraw.Draw(sheet)
            for i, (label, im) in enumerate(sheet_ims):
                x, y = 10 + (i % 2) * (tw + 10), 5 + (i // 2) * (th + 28)
                d.text((x, y + 4), label, fill=(230, 230, 230))
                sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 22))
            sheet.save(out / f"blatt-{name}-s{seed}.jpg", quality=88)
    json.dump(times, open(out / "timings.json", "w"), indent=1)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {out}", flush=True)


if __name__ == "__main__":
    main()
