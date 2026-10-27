"""Manual check (not part of run_all.py): does another Flux 2 Klein 9B int8 file give the same results as ours?

Runs the plugin's own Flux 2 workflows in ComfyUI twice, once with each diffusion model file, with the same prompts,
seeds and settings (Turbo LoRA on, as the tab starts; no LLM prompt writer, so the text is fixed), and writes:
    data/compare-flux2/<time>/<case>_s<seed>_A.png / _B.png    the two results
    data/compare-flux2/<time>/<case>_s<seed>_sheet.png          A | B | difference (x4 brighter)
    data/compare-flux2/<time>/report.md                         time per run, mean difference and PSNR per case

    python tests\\live_flux2_file_compare.py            needs ComfyUI running; uses the GPU (about 16 runs)
    python tests\\live_flux2_file_compare.py --dry      only builds the graphs and checks both files are known to ComfyUI

All A runs go first, then all B runs: the model is loaded once per file; the first run of each file includes loading
and is reported apart. Nothing in the plugin changes.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops  # noqa: E402

from pccomfy import models, workflows  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

FILE_A = "flux-2-klein-9b-int8-ConvRot-comfyui.safetensors"     # the user's copy (Sakujo, no public source any more)
FILE_B = "flux-2-klein-9b_int8_convrot.safetensors"             # obsxrver/ComfyUI-Native-INT8_ConvRot, commit d225df1
SCENE = ROOT / "data" / "test_scene.png"
SEEDS = (1234, 98765)

# (name, workflow, prompt, size or None = the test picture's size, needs the picture)
CASES = [
    ("t2i_fox", "flux2-klein-t2i.json", "A red fox standing in a snowy forest at golden hour, photograph, sharp detail", (1024, 1024), False),
    ("t2i_portrait", "flux2-klein-t2i.json", "Portrait of an elderly fisherman with a grey beard, soft window light, photograph", (768, 1024), False),
    ("edit_night", "flux2-klein-edit.json", "Make it night, with warm street lights and a dark blue sky", None, True),
    ("refine_default", "flux2-klein-upscale.json", models.FLUX2_DEFAULT, None, True),
]


def build(wf: str, prompt: str, size, seed: int, image_name, unet: str) -> tuple[dict, str]:
    tpl = workflows.bypass_prompt_writer(workflows.load_template(ROOT / "workflows" / wf), prompt)
    swapped = 0
    for node in tpl.values():
        if isinstance(node, dict) and node.get("class_type") == "UNETLoader" and node["inputs"].get("unet_name") == FILE_A:
            node["inputs"]["unet_name"] = unet
            swapped += 1
    assert swapped == 1, f"{wf}: expected one UNETLoader with {FILE_A}, found {swapped}"
    p = workflows.GenParams(prompt=prompt, seed=seed, width=size[0], height=size[1])
    if "upscale" in wf:
        p.extra["megapixels"] = size[0] * size[1] / 1e6      # Refine: same size, as the plugin does
    graph, out = workflows.apply_template(tpl, p, image_name, None)
    return graph, out


def psnr(a: Image.Image, b: Image.Image) -> tuple[float, float]:
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    hist = d.histogram()
    n = a.width * a.height * 3
    sq = sum(v * v * c for i in range(3) for v, c in enumerate(hist[i * 256:(i + 1) * 256]))
    ab = sum(v * c for i in range(3) for v, c in enumerate(hist[i * 256:(i + 1) * 256]))
    mse = sq / n
    return ab / n, (99.0 if mse == 0 else 10 * math.log10(255 * 255 / mse))


def sheet(a: Image.Image, b: Image.Image) -> Image.Image:
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).point(lambda v: min(255, v * 4))
    out = Image.new("RGB", (a.width * 3 + 20, a.height), "white")
    for i, im in enumerate((a, b, d)):
        out.paste(im.convert("RGB"), (i * (a.width + 10), 0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="build the graphs only, run nothing")
    args = ap.parse_args()
    comfy = ComfyUI()
    known = comfy._choices("UNETLoader", "unet_name")
    for f in (FILE_A, FILE_B):
        if f not in known:
            raise SystemExit(f"ComfyUI does not list {f} (restart ComfyUI after copying it into diffusion_models).")
    scene = Image.open(SCENE).convert("RGB")
    image_name = None if args.dry else comfy.upload_image(scene, "pccomfy-compare-scene.png")
    jobs = [(c, s) for c in CASES for s in SEEDS]
    for name, wf, prompt, size, needs_img in CASES:
        build(wf, prompt, size or scene.size, SEEDS[0], "x.png" if needs_img else None, FILE_B)
    if args.dry:
        print(f"ok: both files known to ComfyUI, {len(CASES)} cases x {len(SEEDS)} seeds x 2 files = {len(jobs) * 2} runs")
        return
    out_dir = ROOT / "data" / "compare-flux2" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    times = {}
    for tag, unet in (("A", FILE_A), ("B", FILE_B)):
        for k, ((name, wf, prompt, size, needs_img), seed) in enumerate(jobs):
            graph, out = build(wf, prompt, size or scene.size, seed, image_name if needs_img else None, unet)
            t0 = time.monotonic()
            pid = comfy.queue(graph)
            hist = comfy.wait(pid)
            secs = time.monotonic() - t0
            im = comfy.output_images(hist, out)[0]
            im.save(out_dir / f"{name}_s{seed}_{tag}.png")
            times[(tag, name, seed)] = (secs, k == 0)
            print(f"{tag} {name} seed {seed}: {secs:.1f} s" + ("  (includes loading the model)" if k == 0 else ""))
    rows = ["| case | seed | time A (s) | time B (s) | mean diff (0-255) | PSNR (dB) |", "|---|---|---|---|---|---|"]
    for (name, *_), seed in jobs:
        a = Image.open(out_dir / f"{name}_s{seed}_A.png")
        b = Image.open(out_dir / f"{name}_s{seed}_B.png")
        if a.size != b.size:
            b = b.resize(a.size)
        mae, db = psnr(a, b)
        sheet(a, b).save(out_dir / f"{name}_s{seed}_sheet.png")
        ta, la = times[("A", name, seed)]
        tb, lb = times[("B", name, seed)]
        rows.append(f"| {name} | {seed} | {ta:.1f}{' *' if la else ''} | {tb:.1f}{' *' if lb else ''} | {mae:.2f} | {db:.1f} |")
    warm = lambda tag: [s for (t, _, _), (s, first) in times.items() if t == tag and not first]   # noqa: E731
    avg = lambda xs: sum(xs) / len(xs) if xs else 0.0                                             # noqa: E731
    report = ["# Flux 2 Klein 9B: file A vs file B", "",
              f"A = `{FILE_A}` (the user's copy), B = `{FILE_B}` (obsxrver, d225df1).",
              "Turbo LoRA on, no LLM prompt writer, same seeds. * = first run of that file (includes loading).", "",
              *rows, "",
              f"Average time without the first run: A {avg(warm('A')):.1f} s, B {avg(warm('B')):.1f} s.", "",
              "Reading: PSNR above about 35 dB = practically the same picture; 25 to 35 dB = small differences in detail;",
              "below 25 dB = a visibly different picture (same composition can still differ). Judge the sheets by eye."]
    (out_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (out_dir / "cases.json").write_text(json.dumps([dict(name=c[0], workflow=c[1], prompt=c[2]) for c in CASES], indent=1), encoding="utf-8")
    print("\n".join(report))
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
