"""Manual check (not part of run_all.py): Fibo Text to image with and without the LLM prompt writer, blind (user 30.10.).

Fibo Text to image now has the LLM writer of Fibo Edit (Qwen 3.5 9B int8 ConvRot) with Bria's own "Generate" system
prompt: it turns the short prompt into Fibo's structured JSON (VGL) prompt. This round runs every prompt and seed once
with the typed prompt and once with the LLM, everything else as the plugin's start settings, and the user rates each
pair blind (left / right in random order).

The prompts are a mix of docs/tests/testprompts.md (ImageBench): text, counting, position, faces, motion, colours, layout.

    python tests\\live_fibo_llm.py run [--seeds 2] [--size 1216]
    python tests\\live_fibo_llm.py rate          (the newest round; or give its folder)
    python tests\\live_fibo_llm.py summary       (wins with / without LLM, also written to ergebnis.md)

Output: data\\fibo-llm-test\\<time>\\ (pictures, the LLM's JSON per picture, key.json, bewertung.json, ergebnis.md).
Needs ComfyUI with the Fibo files and qwen3.5_9b_int8_convrot.safetensors; nothing in the plugin changes.
"""
import argparse
import json
import random
import re
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

BASE = cfgmod.CONFIG_DIR / "fibo-llm-test"
WF = ROOT / "workflows" / "fibo2-t2i.json"
PROMPT_FILE = ROOT / "docs" / "tests" / "testprompts.md"
# one or two of each kind: text, counting, position, faces, motion, colours, layout
PROMPTS = [1, 12, 25, 40, 55, 73, 90, 101, 120, 143, 160, 180]
VARIANTS = (False, True)            # LLM prompt enhancement off / on


class _NoPhotoCraft:
    pass


def prompts() -> dict[int, str]:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    found = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^(\d+)\. (.+)$", text, re.M)}
    return {n: found[n] for n in PROMPTS}


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
    seeds = [101, 202, 303, 404][: max(1, a.seeds)]
    ps = prompts()
    key, pairs, n, t_start = {}, [], 0, time.time()
    variants = VARIANTS
    total = len(ps) * len(seeds) * len(variants)
    for num, prompt in ps.items():
        for seed in seeds:
            pair = []
            for llm in variants:
                n += 1
                t0 = time.time()
                # the plugin's start settings of Fibo Text to image; only the LLM switch differs
                req = Request(mode="txt2img", workflow=str(WF), enhance=llm)
                p = workflows.GenParams(prompt=prompt, seed=seed, width=a.size, height=a.size)
                graph, out_node = b._graph(req, p, None, None, str(WF), force_plain=not llm)
                hist = b._wait(b.comfy.queue(graph), graph, str(WF), 0, 1, "", lambda *x, **k: None)
                im = b.comfy.output_images(hist, out_node)[0].convert("RGB")
                fid = f"{len(key) + 1:04d}"
                im.save(out / "bilder" / f"{fid}.png")
                if llm:                          # what the LLM wrote (the pc:vgl preview node), for the notes
                    vgl = hist.get("outputs", {}).get("23", {}).get("text") or [""]
                    (out / "bilder" / f"{fid}.json").write_text(str(vgl[0]), encoding="utf-8")
                key[fid] = {"prompt_nr": num, "seed": seed, "llm": llm}
                pair.append(fid)
                print(f"{n}/{total} prompt {num} seed {seed} LLM {'on' if llm else 'off'}: {time.time() - t0:.0f} s", flush=True)
            pairs.append(pair)
    rnd = random.Random(7)
    rnd.shuffle(pairs)
    for pair in pairs:
        rnd.shuffle(pair)                # which one had the LLM is hidden
    json.dump({"pairs": pairs, "items": key, "prompts": ps, "size": a.size},
              open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {len(key)} pictures in {out}\n"
          f"Next: python tests\\live_fibo_llm.py rate", flush=True)


def label(it: dict) -> str:
    return "mit LLM" if it["llm"] else "ohne LLM"


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
    root.title("Fibo Text to image: LLM blind vergleichen")
    root.configure(bg="#282828")
    st = {"i": 0}
    choice, note = tk.StringVar(), tk.StringVar()
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"), wraplength=1800, justify="left")
    top.pack(pady=(8, 4))
    row = tk.Frame(root, bg="#282828")
    row.pack()
    pics = [tk.Label(row, bg="#282828") for _ in range(2)]
    for i, p in enumerate(pics):
        p.pack(side="left", padx=6)
    side = tk.Frame(root, bg="#282828")
    side.pack(pady=6)
    kw = dict(bg="#282828", selectcolor="#535353", activebackground="#282828", activeforeground="#ffffff",
              font=("Segoe UI", 11), command=lambda: save())
    for k, (label, val) in enumerate((("links besser", "links"), ("gleich gut", "gleich"), ("rechts besser", "rechts"),
                                      ("beide schlecht", "beide schlecht")), 1):
        tk.Radiobutton(side, text=f"{label} ({k})", variable=choice, value=val, fg="#e6e6e6", **kw).pack(side="left", padx=8)
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
    st["loading"] = False

    def count():
        status.configure(text=f"bewertet: {sum(1 for i in range(len(pairs)) if data.get(str(i), {}).get('wahl'))}/"
                              f"{len(pairs)}  ·  gespeichert in {fout}")

    def show():
        i = st["i"]
        left, right = pairs[i]
        it = items[left]
        top.configure(text=f"Paar {i + 1}/{len(pairs)}  ·  Prompt {it['prompt_nr']}: {key['prompts'][str(it['prompt_nr'])]}")
        side_px = min((root.winfo_screenwidth() - 60) // 2, root.winfo_screenheight() - 260)
        st["photos"] = []
        for lbl, fid in zip(pics, (left, right)):
            im = Image.open(out / "bilder" / f"{fid}.png").convert("RGB")
            im.thumbnail((side_px, side_px))
            ph = ImageTk.PhotoImage(im)
            st["photos"].append(ph)
            lbl.configure(image=ph)
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
    labels = list(dict.fromkeys(label(it) for it in items.values()))       # the two variants, in run order
    wins = {c: 0 for c in labels}
    same = bad = 0
    per_prompt = {}
    for rec in data.values():
        w = rec.get("wahl")
        if not w:
            continue
        num = items[rec["links"]]["prompt_nr"]
        pp = per_prompt.setdefault(num, {c: 0 for c in labels} | {"gleich": 0, "beide schlecht": 0})
        if w in ("links", "rechts"):
            c = label(items[rec[w]])
            wins[c] += 1
            pp[c] += 1
        elif w == "gleich":
            same += 1
            pp["gleich"] += 1
        else:
            bad += 1
            pp["beide schlecht"] += 1
    rated = sum(1 for r in data.values() if r.get("wahl"))
    a_, b_ = labels
    lines = [f"# Fibo-LLM-Testrunde {out.name}", "", f"Bewertet: {rated} von {len(key['pairs'])} Paaren "
             f"({key.get('size', '?')} px, Startwerte von Fibo Text to image)", "",
             f"| {a_} besser | {b_} besser | gleich gut | beide schlecht |", "|---|---|---|---|",
             f"| {wins[a_]} | {wins[b_]} | {same} | {bad} |", "", "Je Prompt:", "",
             f"| Prompt | {a_} | {b_} | gleich | beide schlecht |", "|---|---|---|---|---|"]
    for num in sorted(per_prompt):
        pp = per_prompt[num]
        lines.append(f"| {num} | {pp[a_]} | {pp[b_]} | {pp['gleich']} | {pp['beide schlecht']} |")
    notes = [(r, r["notiz"]) for r in data.values() if r.get("notiz")]
    if notes:
        lines += ["", "Notizen:"] + [f"- Prompt {items[r['links']]['prompt_nr']} (links {label(items[r['links']])}, "
                                     f"rechts {label(items[r['rechts']])}): {n}" for r, n in notes]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--seeds", type=int, default=2, help="seeds per prompt (1 to 4)")
    r.add_argument("--size", type=int, default=1216, help="width and height in px (near the plugin's base res. for Fibo)")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
