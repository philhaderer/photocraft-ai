"""Manual check (not part of run_all.py): the Styles button on Text to image, all six models, blind (PLAN.md point 16, user 1.11.).

Zuschnitt A (decided 1.11.): 10 realistic prompts of docs/tests/testprompts.md (the same as the MOSS CFG round), each with ONE
style (PLAN_STYLES below, one style per prompt, spread over the groups) and once without a style; 6 models, 2 seeds each, every
model with the plugin's standard settings for Text to image (the real window code builds the request, saved pages are ignored).
10 prompts x 2 (plain / styled) x 2 seeds x 6 models = 240 pictures. The style text is added after a line break, exactly like
the button does it. The user rates each pair blind (left / right in random order).

    python tests\\live_style_test.py plan                      (what would run; no ComfyUI needed)
    python tests\\live_style_test.py run [--seeds 2] [--models flux3 moss ...] [--dry]
    python tests\\live_style_test.py rate [folder]             (the same window as the MOSS round)
    python tests\\live_style_test.py summary [folder]          (wins per model and per style, written to ergebnis.md)
    python tests\\live_style_test.py sheets [folder]           (one contact sheet per model, plain | styled; shows the key, use it after rating)

Output: data\\style-test\\<time>\\ (pictures, key.json, bewertung.json, ergebnis.md, blatt-<model>.png). Needs ComfyUI with the
files of the models; nothing in the plugin changes. ``--dry`` builds every graph but queues nothing (no GPU, no ComfyUI).
"""
import argparse
import json
import random
import re
import socket
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402

import live_moss_cfg as rater  # noqa: E402  (the rating window and the helpers of the MOSS round)
from pccomfy import config as cfgmod, gui, imaging, inventory, models, styles, workflows  # noqa: E402
from pccomfy.bridge import Bridge  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "style-test"
rater.BASE = BASE
PROMPT_FILE = ROOT / "docs" / "tests" / "testprompts.md"
MODELS = ("flux3", "flux2", "qwen", "fibo", "moss", "krea2")
SEEDS = (101, 202, 303, 404)
# prompt number -> style name (looked up by name in pccomfy/assets/styles.json, Text to image)
PLAN_STYLES = {73: "Amber Dusk", 74: "Blue Rim Light", 79: "Seventies Film", 81: "Harsh Flash Film", 115: "High-Key White",
               116: "Blue Hour Haze", 143: "Macro Refraction", 144: "Tilt-Shift Miniature", 166: "Neon Bokeh Night",
               168: "Colour Field Aura"}


class _NoPhotoCraft:
    pass


def prompts() -> dict[int, str]:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    found = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^(\d+)\. (.+)$", text, re.M)}
    return {n: found[n] for n in PLAN_STYLES}


def style_texts() -> dict[str, str]:
    """Style name -> its text, from the data of the Styles button (Text to image)."""
    allst = {s["name"]: s["text"] for g in styles.load().get("txt2img", []) for s in g["styles"]}
    missing = [n for n in PLAN_STYLES.values() if n not in allst]
    if missing:
        sys.exit(f"Styles not in pccomfy/assets/styles.json: {missing}")
    return {n: allst[n] for n in PLAN_STYLES.values()}


def cmd_plan(a):
    ps, st = prompts(), style_texts()
    for num, prompt in ps.items():
        print(f"{num}: {prompt[:90]}\n     style {PLAN_STYLES[num]}: {st[PLAN_STYLES[num]][:110]}")
    print(f"\n{len(ps)} prompts x 2 x {a.seeds} seeds x {len(a.models)} models = {len(ps) * 2 * a.seeds * len(a.models)} pictures")


def make_app(url: str):
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = url
    cfg["photocraft"]["port"] = 1             # no PhotoCraft needed
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names      # the workflow list is read from ComfyUI otherwise
    return app


def standard_request(app, key: str):
    """The Request the plugin would send for Text to image with this model's standard settings (saved pages ignored)."""
    app.v_model.set(key)
    app.v_mode.set("txt2img")
    app._factory = True
    try:
        app._on_model()
        app._on_mode()
    finally:
        app._factory = False
    app.t_prompt.delete("1.0", "end")
    return app._request(), app._model().label


def cmd_run(a):
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    if not a.dry:
        try:
            socket.create_connection((host, port), timeout=2).close()
        except OSError:
            sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    ps, st = prompts(), style_texts()
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True)
    comfy = ComfyUI(url)
    b = Bridge(_NoPhotoCraft(), comfy, out / "xch")
    app = make_app(url)
    inv = None if a.dry else inventory.fetch(comfy, cfgmod.model_map())
    seeds = list(SEEDS[: max(1, a.seeds)])
    key, pairs, t_start, n = {}, [], time.time(), 0
    for mk in a.models:
        if inv is not None and inv.tab_status(mk).state != "ready":
            print(f"SKIPPED {mk}: its files are not all there", flush=True)
            continue
        req, label = standard_request(app, mk)
        wf = req.workflow
        tpl = workflows.load_template(wf)
        gw, gh = imaging.gen_size(1000, 1000, req.base_res, multiple=max(workflows.size_multiple(tpl), 1))
        needs_image = any(isinstance(nd, dict) and nd.get("_meta", {}).get("title") == "pc:image" for nd in tpl.values())
        print(f"== {label}: {Path(wf).name}, {gw}x{gh}, steps {req.params.steps}, cfg {req.params.cfg}, "
              f"sampler_override {req.sampler_override}, turbo {req.turbo}, sharpen {req.sharpen}", flush=True)
        for num, prompt in ps.items():
            for seed in seeds:
                pair = []
                for styled in (False, True):
                    n += 1
                    text = prompt + ("\n" + st[PLAN_STYLES[num]] if styled else "")       # as the Styles button adds it
                    p = replace(req.params, prompt=text, seed=seed, width=gw, height=gh)
                    image_name = None
                    if needs_image:       # Qwen Edit as Text to image: an empty white canvas of the result's size (as the bridge does)
                        image_name = "dry.png" if a.dry else comfy.upload_image(Image.new("RGB", (gw, gh), "white"), f"pcc-style-{n}.png")
                    graph, out_node = b._graph(req, p, image_name, None, wf)
                    fid = f"{len(key) + 1:04d}"
                    key[fid] = {"prompt_nr": num, "seed": seed, "model": label, "model_key": mk, "styled": styled,
                                "style": PLAN_STYLES[num] if styled else "none"}
                    pair.append(fid)
                    if a.dry:
                        continue
                    t0 = time.time()
                    hist = b._wait(comfy.queue(graph), graph, str(wf), 0, 1, "", lambda *x, **k: None)
                    im = comfy.output_images(hist, out_node)[0].convert("RGB")
                    if req.sharpen:
                        im = imaging.sharpen(im, req.sharpen)
                    im.save(out / "bilder" / f"{fid}.png")
                    print(f"{n} {label} prompt {num} seed {seed} {'styled' if styled else 'plain '}: {time.time() - t0:.0f} s", flush=True)
                pairs.append(pair)
    rnd = random.Random(11)
    rnd.shuffle(pairs)
    for pair in pairs:
        rnd.shuffle(pair)                # which one is left is hidden
    json.dump({"pairs": pairs, "items": key, "prompts": {str(k): v for k, v in ps.items()}, "title": "Styles: blind vergleichen",
               "styles": {str(k): v for k, v in PLAN_STYLES.items()}}, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\n{'DRY RUN (nothing queued)' if a.dry else 'DONE'} in {(time.time() - t_start) / 60:.1f} min: {len(key)} pictures in {out}\n"
          f"Next: python tests\\live_style_test.py rate", flush=True)
    app.root.destroy()


def cmd_summary(a):
    out = rater.latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    data = json.loads((out / "bewertung.json").read_text(encoding="utf-8")) if (out / "bewertung.json").exists() else {}
    items = key["items"]
    per = {}                                   # (kind, name) -> counts
    cols = ["Stil besser", "ohne Stil besser", "gleich", "beide schlecht"]
    tot = dict.fromkeys(cols, 0)
    for rec in data.values():
        w = rec.get("wahl")
        if not w:
            continue
        left, right = items[rec["links"]], items[rec["rechts"]]
        field = "gleich" if w == "gleich" else "beide schlecht" if w == "beide schlecht" else (
            "Stil besser" if items[rec[w]]["styled"] else "ohne Stil besser")
        tot[field] += 1
        style = left["style"] if left["styled"] else right["style"]
        for k in (("Modell", left["model"]), ("Stil", style)):
            row = per.setdefault(k, dict.fromkeys(cols, 0))
            row[field] += 1
    rated = sum(1 for r in data.values() if r.get("wahl"))
    lines = [f"# Stil-Testrunde {out.name}", "", f"Bewertet: {rated} von {len(key['pairs'])} Paaren (blind, Standardeinstellungen je Modell)", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols), "| " + " | ".join(str(tot[c]) for c in cols) + " |"]
    for kind in ("Modell", "Stil"):
        lines += ["", f"Je {kind}:", "", f"| {kind} | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for (k, name), row in sorted(per.items(), key=lambda x: x[0][1]):
            if k == kind:
                lines.append(f"| {name} | " + " | ".join(str(row[c]) for c in cols) + " |")
    notes = [(r, r["notiz"]) for r in data.values() if r.get("notiz")]
    if notes:
        lines += ["", "Notizen:"] + [f"- {items[r['links']]['model']}, Prompt {items[r['links']]['prompt_nr']}: {n}" for r, n in notes]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def cmd_sheets(a):
    """One contact sheet per model: a row per prompt, the columns plain | styled for each seed."""
    out = rater.latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    items, th = key["items"], 256
    for mk in dict.fromkeys(i["model_key"] for i in items.values()):
        rows = {}
        for fid, it in items.items():
            if it["model_key"] == mk:
                rows.setdefault(it["prompt_nr"], {})[(it["seed"], it["styled"])] = fid
        seeds = sorted({s for r in rows.values() for s, _ in r})
        cols = [(s, st) for s in seeds for st in (False, True)]
        sheet = Image.new("RGB", (len(cols) * th, len(rows) * (th + 18)), "#282828")
        d = ImageDraw.Draw(sheet)
        for y, num in enumerate(sorted(rows)):
            for x, c in enumerate(cols):
                f = out / "bilder" / f"{rows[num].get(c, '')}.png"
                if f.exists():
                    im = Image.open(f).convert("RGB")
                    im.thumbnail((th, th))
                    sheet.paste(im, (x * th, y * (th + 18) + 18))
                d.text((x * th + 4, y * (th + 18) + 3),
                       f"{num} seed {c[0]} " + (f"STYLED {key['styles'].get(str(num), '')}" if c[1] else "plain"), fill="#e6e6e6")
        sheet.save(out / f"blatt-{mk}.png")
        print(f"blatt-{mk}.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        r = sub.add_parser(name)
        r.add_argument("--seeds", type=int, default=2, help="seeds per prompt (1 to 4)")
        r.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
        r.add_argument("--dry", action="store_true", help="build all graphs, queue nothing")
    for name in ("rate", "summary", "sheets"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"plan": cmd_plan, "run": cmd_run, "rate": rater.cmd_rate, "summary": cmd_summary, "sheets": cmd_sheets}[a.cmd](a)


if __name__ == "__main__":
    main()
