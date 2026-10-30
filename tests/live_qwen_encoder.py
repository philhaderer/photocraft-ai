"""Manual check (not part of run_all.py): Qwen 2.1 Edit with its two Qwen3-VL 8B text encoder files, blind (user 30.10.).

Qwen 2.1 loads Qwen3-VL 8B twice over: the edit graph (Edit, Fill, Expand, Remove, Multi Image Edit) as fp8_scaled
(10.6 GB), the text-to-image graph as int8_convrot (9.4 GB). If the edit graph is as good with int8_convrot, Qwen needs
only that one file. This round runs Qwen Edit on the user's test pictures with each file (same prompt, seed and settings
as the tab starts: no Turbo LoRA, base res. 1024; only the text encoder differs), and the user rates each pair blind
(left / right in random order, the original above them).

    python tests\\live_qwen_encoder.py run [--images C:\\programs\\testpics3\\resized_1280px] [--count 6] [--seeds 1]
    python tests\\live_qwen_encoder.py rate          (the newest round; or give its folder)
    python tests\\live_qwen_encoder.py summary       (wins per file, also written to ergebnis.md)

Output: data\\qwen-encoder-test\\<time>\\ (pictures, key.json, bewertung.json, ergebnis.md). Needs ComfyUI with both files;
nothing in the plugin changes. All runs of one file go first, so each encoder is loaded once.
"""
import argparse
import json
import math
import random
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import config as cfgmod, workflows  # noqa: E402
from pccomfy.bridge import Bridge, Request  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "qwen-encoder-test"
WF = ROOT / "workflows" / "qwen-image-21-edit.json"
IMAGES = Path(r"C:\programs\testpics3\resized_1280px")
FILES = ("qwen3vl_8b_fp8_scaled.safetensors", "qwen3vl_8b_int8_convrot.safetensors")
NAMES = {FILES[0]: "fp8_scaled", FILES[1]: "int8_convrot"}
# edits that fit any photo: light, season, style, weather, an object
PROMPTS = ["Make it night, with warm street lights and a dark blue sky",
           "Turn it into a watercolour painting with soft paper texture",
           "Make it winter: snow on the ground and on every surface",
           "Add soft morning fog in the background",
           "Change the season to autumn with orange and red leaves",
           "Make it look like an old film photograph from the 1970s"]


class _NoPhotoCraft:
    pass


def one_megapixel(im: Image.Image, base: int = 1024) -> Image.Image:
    """The picture at about base x base pixels, sides a multiple of 16 (as the plugin sends an Edit at base res. 1024)."""
    f = math.sqrt(base * base / (im.width * im.height))
    w, h = max(16, round(im.width * f / 16) * 16), max(16, round(im.height * f / 16) * 16)
    return im.convert("RGB").resize((w, h), Image.LANCZOS)


def cmd_run(a):
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    comfy = ComfyUI(url)
    known = comfy._choices("CLIPLoader", "clip_name")
    for f in FILES:
        if f not in known:
            sys.exit(f"ComfyUI does not list {f} (copy it into text_encoders and restart ComfyUI).")
    pics = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[: a.count]
    if not pics:
        sys.exit(f"No pictures in {a.images}")
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True)
    b = Bridge(_NoPhotoCraft(), comfy, out / "xch")
    seeds = [101, 202, 303][: max(1, a.seeds)]
    cases = []                                      # (case id, picture, prompt, seed, uploaded name, size)
    for i, pic in enumerate(pics):
        im = one_megapixel(Image.open(pic))
        cid = f"c{i + 1:02d}"
        im.save(out / "bilder" / f"{cid}_original.png")
        name = comfy.upload_image(im, f"pccomfy-encoder-{cid}.png")
        for seed in seeds:
            cases.append((f"{cid}s{seed}", pic.name, PROMPTS[i % len(PROMPTS)], seed, name, im.size))
    key, by_case, n, t_start = {}, {}, 0, time.time()
    total = len(cases) * len(FILES)
    for enc in FILES:
        for cid, pic, prompt, seed, name, (w, h) in cases:
            n += 1
            t0 = time.time()
            # the tab's start settings: no Turbo LoRA, no LLM; only the text encoder differs
            req = Request(mode="edit", workflow=str(WF), enhance=False, turbo=False)
            p = workflows.GenParams(prompt=prompt, seed=seed, width=w, height=h)
            graph, out_node = b._graph(req, p, name, None, str(WF))
            swapped = 0
            for node in graph.values():
                if isinstance(node, dict) and node.get("class_type") == "CLIPLoader" and node["inputs"].get("clip_name") in FILES:
                    node["inputs"]["clip_name"] = enc
                    swapped += 1
            assert swapped == 1, f"expected one Qwen3-VL text encoder in the edit graph, found {swapped}"
            hist = b._wait(comfy.queue(graph), graph, str(WF), 0, 1, "", lambda *x, **k: None)
            im = comfy.output_images(hist, out_node)[0].convert("RGB")
            fid = f"{len(key) + 1:04d}"
            im.save(out / "bilder" / f"{fid}.png")
            key[fid] = {"case": cid, "picture": pic, "prompt": prompt, "seed": seed, "encoder": NAMES[enc]}
            by_case.setdefault(cid, []).append(fid)
            print(f"{n}/{total} {NAMES[enc]} {pic} seed {seed}: {time.time() - t0:.0f} s"
                  + ("  (includes loading)" if n in (1, len(cases) + 1) else ""), flush=True)
    rnd = random.Random(7)
    pairs = list(by_case.values())
    rnd.shuffle(pairs)
    for pair in pairs:
        rnd.shuffle(pair)                # which file is left is hidden
    json.dump({"pairs": pairs, "items": key}, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {len(key)} pictures in {out}\n"
          f"Next: python tests\\live_qwen_encoder.py rate", flush=True)


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
    pairs, items = key["pairs"], key["items"]
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title("Qwen Edit: Text-Encoder blind vergleichen")
    root.configure(bg="#282828")
    st = {"i": 0, "loading": False}
    choice, note = tk.StringVar(), tk.StringVar()
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"), wraplength=1800, justify="left")
    top.pack(pady=(8, 4))
    orig = tk.Label(root, bg="#282828")
    orig.pack()
    row = tk.Frame(root, bg="#282828")
    row.pack(pady=(6, 0))
    pics = [tk.Label(row, bg="#282828") for _ in range(2)]
    for p in pics:
        p.pack(side="left", padx=6)
    side = tk.Frame(root, bg="#282828")
    side.pack(pady=6)
    kw = dict(bg="#282828", selectcolor="#535353", activebackground="#282828", activeforeground="#ffffff",
              font=("Segoe UI", 11), command=lambda: save())
    for k, (text, val) in enumerate((("links besser", "links"), ("gleich gut", "gleich"), ("rechts besser", "rechts"),
                                     ("beide schlecht", "beide schlecht")), 1):
        tk.Radiobutton(side, text=f"{text} ({k})", variable=choice, value=val, fg="#e6e6e6", **kw).pack(side="left", padx=8)
    nf = tk.Frame(root, bg="#282828")
    nf.pack(pady=4)
    tk.Label(nf, text="Notiz:", bg="#282828", fg="#cfcfcf").pack(side="left")
    ent = tk.Entry(nf, textvariable=note, bg="#535353", fg="#ffffff", insertbackground="#ffffff", width=90)
    ent.pack(side="left", padx=6)
    nav = tk.Frame(root, bg="#282828")
    nav.pack(pady=4)
    tk.Button(nav, text="← Zurück", command=lambda: go(-1)).pack(side="left")
    tk.Button(nav, text="Weiter →", command=lambda: go(1)).pack(side="left", padx=8)
    status = tk.Label(nav, bg="#282828", fg="#9a9a9a")
    status.pack(side="left", padx=16)

    def count():
        status.configure(text=f"bewertet: {sum(1 for i in range(len(pairs)) if data.get(str(i), {}).get('wahl'))}/"
                              f"{len(pairs)}  ·  gespeichert in {fout}")

    def photo(path, box):
        im = Image.open(path).convert("RGB")
        im.thumbnail(box)
        ph = ImageTk.PhotoImage(im)
        st["photos"].append(ph)
        return ph

    def show():
        i = st["i"]
        left, right = pairs[i]
        it = items[left]
        top.configure(text=f"Paar {i + 1}/{len(pairs)}  ·  {it['picture']}  ·  Prompt: {it['prompt']}")
        h = root.winfo_screenheight()
        side_px = min((root.winfo_screenwidth() - 60) // 2, int(h * 0.55))
        st["photos"] = []
        orig.configure(image=photo(out / "bilder" / f"{it['case'][:3]}_original.png", (int(h * 0.22), int(h * 0.22))))
        for lbl, fid in zip(pics, (left, right)):
            lbl.configure(image=photo(out / "bilder" / f"{fid}.png", (side_px, side_px)))
        st["loading"] = True
        rec = data.get(str(i), {})
        choice.set(rec.get("wahl", ""))
        note.set(rec.get("notiz", ""))
        st["loading"] = False
        count()

    def save():
        if st["loading"]:
            return
        i = st["i"]
        data[str(i)] = {"links": pairs[i][0], "rechts": pairs[i][1], "wahl": choice.get(), "notiz": note.get().strip()}
        fout.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        count()

    def go(step):
        st["i"] = max(0, min(len(pairs) - 1, st["i"] + step))
        show()

    def key_press(e):
        if root.focus_get() is ent:
            return
        if e.char in ("1", "2", "3", "4"):
            choice.set({"1": "links", "2": "gleich", "3": "rechts", "4": "beide schlecht"}[e.char])
            save()
            root.after(250, lambda: go(1))
        elif e.keysym in ("Right", "Left"):
            go(1 if e.keysym == "Right" else -1)

    note.trace_add("write", lambda *x: save())
    root.bind("<Key>", key_press)
    root.bind("<Button-1>", lambda e: root.focus_set() if e.widget in pics else None)
    root.state("zoomed")
    show()
    root.mainloop()


def cmd_summary(a):
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    items = key["items"]
    wins = {n: 0 for n in NAMES.values()}
    same = bad = 0
    for rec in data.values():
        w = rec.get("wahl")
        if w in ("links", "rechts"):
            wins[items[rec[w]]["encoder"]] += 1
        elif w == "gleich":
            same += 1
        elif w:
            bad += 1
    rated = sum(1 for r in data.values() if r.get("wahl"))
    a_, b_ = NAMES.values()
    lines = [f"# Qwen Edit Text-Encoder-Testrunde {out.name}", "", f"Bewertet: {rated} von {len(key['pairs'])} Paaren "
             "(Qwen 2.1 Edit, ohne Turbo, ohne LLM, Basis 1024)", "",
             f"| {a_} besser | {b_} besser | gleich gut | beide schlecht |", "|---|---|---|---|",
             f"| {wins[a_]} | {wins[b_]} | {same} | {bad} |"]
    notes = [r for r in data.values() if r.get("notiz")]
    if notes:
        lines += ["", "Notizen:"] + [f"- {items[r['links']]['picture']} (links {items[r['links']]['encoder']}, "
                                     f"rechts {items[r['rechts']]['encoder']}): {r['notiz']}" for r in notes]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--images", default=str(IMAGES), help="folder with the test pictures")
    r.add_argument("--count", type=int, default=6, help="how many pictures (each gets one edit prompt)")
    r.add_argument("--seeds", type=int, default=1, help="seeds per picture (1 to 3)")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
