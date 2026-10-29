"""Seam correction as an A/B test (OpenFill T2, user 28.10.): the tone difference where the result must match the
original is measured, smoothed and added to the whole result (imaging.seam_correct). With the switch on, each result
comes twice: "[seam fix]" on top and visible, "[raw]" hidden below it; the tone jump of #1 before and after goes into
the result (status line) and runs.jsonl. Off (the default at every start): nothing changes. Per model (user 29.10.):
Fibo always corrects (one layer, no checkbox), Flux 2 / 3 never (no checkbox), Qwen keeps the checkbox. Stubbed Tk,
PhotoCraft and ComfyUI.

    python tests/test_seam_correction.py
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
import test_reference_mode as t  # noqa: E402

from pccomfy import imaging, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

ROOT = t.ROOT


def picture():
    """An original with structure and grain, a selection with a new object, and a result whose tone is shifted
    (more on the right): the lighter rim of the sky test."""
    rng = np.random.default_rng(1)
    h, w = 384, 480
    yy, xx = np.mgrid[0:h, 0:w]
    orig = np.stack([100 + 60 * np.sin(xx / 40), 120 + 40 * np.cos(yy / 30), 90 + 0 * xx], -1) + rng.normal(0, 6, (h, w, 3))
    orig = np.clip(orig, 0, 255)
    mask = np.zeros((h, w), np.uint8)
    mask[120:260, 150:330] = 255
    gen = orig.copy()
    gen[mask > 0] = 200 + rng.normal(0, 10, (int((mask > 0).sum()), 3))
    gen = np.clip(gen + 8 + 0.02 * xx[..., None], 0, 255)
    return (Image.fromarray(orig.astype(np.uint8)), Image.fromarray(gen.astype(np.uint8)), Image.fromarray(mask))


def imaging_checks():
    orig, gen, mask = picture()
    fixed = imaging.seam_correct(gen, orig, mask)
    before, after = imaging.seam_jump(gen, orig, mask), imaging.seam_jump(fixed, orig, mask)
    assert before > 10 and after < 1, (before, after)
    o, g, f = (np.asarray(x, float) for x in (orig, gen, fixed))
    out = np.asarray(mask) == 0
    assert np.abs(f - o)[out].mean() < 1 < np.abs(g - o)[out].mean()          # the surroundings meet the original
    hp = lambda im: np.asarray(im.convert("L"), float) - np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(8)), float)
    assert np.abs(hp(fixed) - hp(gen))[np.asarray(mask) > 0].mean() < 0.5     # the detail stays as the model drew it
    # a changed object outside the selection (a shadow) is not taken as a tone shift
    g2 = np.asarray(fixed).copy()
    g2[270:300, 150:330] = 20
    shadow = Image.fromarray(g2)
    assert np.abs(np.asarray(imaging.seam_correct(shadow, orig, mask), float) - g2)[out].mean() < 1
    # nothing to measure: unchanged
    full = Image.new("L", gen.size, 255)
    assert imaging.seam_correct(gen, orig, full) is gen and imaging.seam_jump(gen, orig, full) == 0.0
    assert imaging.seam_correct(gen, orig, Image.new("L", gen.size, 0)) is gen
    # the same result as the original: nothing to correct
    same = imaging.seam_correct(orig, orig, mask)
    assert np.abs(np.asarray(same, float) - o).max() <= 1


def run(seam, variants=1, mode="inpaint", remove=False, wf="qwen-image-21-edit.json", fixed=False):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode=mode, workflow=str(ROOT / "workflows" / wf), enhance=False, remove=remove, seam=seam, seam_fixed=fixed,
                  variants=variants, layer_mask="soft")
    req.params = workflows.GenParams(prompt="a boat", seed=7)
    res = b.run(req)
    names = {p["layer"]: p["name"] for c, p in pc.log if c == "layer.renameLayer"}
    hidden = {p["layer"] for c, p in pc.log if c == "layer.hideLayers"}
    return res, [names[lid] for lid in res["layers"]], [lid in hidden for lid in res["layers"]], b


def bridge_checks():
    res, names, hidden, _ = run(seam=False)
    assert len(names) == 1 and "[raw]" not in names[0] and "[seam fix]" not in names[0] and res["seam"] is None
    res, names, hidden, b = run(seam=True)
    assert len(names) == 2, names
    assert "[seam fix]" in names[0] and "[raw]" in names[1], names    # corrected on top
    assert hidden == [False, True], hidden
    assert res["group"] is not None                       # the pair goes into the variants' group
    before, after = res["seam"]
    assert before >= 0 and after >= 0
    rec = [json.loads(x) for x in (b.exchange / "runs.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert rec["seam_before"] == round(before, 1) and rec["seam_after"] == round(after, 1)
    # two variants: a pair each, only #1's corrected layer visible
    two = lambda self, hist, node_id=None: [Image.new("RGB", (64, 64), (10, 200, 10)), Image.new("RGB", (64, 64), (200, 10, 10))]
    old, t.FakeComfy.output_images = t.FakeComfy.output_images, two
    try:
        res, names, hidden, _ = run(seam=True, variants=2)
    finally:
        t.FakeComfy.output_images = old
    assert len(names) == 4 and hidden == [False, True, True, True], (names, hidden)
    assert [n.endswith("#1") for n in names] == [True, True, False, False], names
    # Remove too
    res, names, hidden, _ = run(seam=True, mode="remove", wf="fibo2-edit.json")
    assert len(names) == 2 and "[seam fix]" in names[0], names
    # always on (Fibo, user 29.10.): one corrected layer, a plain name, no number in the status line, but in runs.jsonl
    res, names, hidden, b = run(seam=False, fixed=True, wf="fibo2-edit.json")
    assert len(names) == 1 and "[seam fix]" not in names[0] and "[raw]" not in names[0], names
    assert res["seam"] is None and res["group"] is None
    rec = [json.loads(x) for x in (b.exchange / "runs.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert rec["seam"] == "on" and "seam_before" in rec and "seam_after" in rec, rec


def gui_checks():
    app = ra.make()
    shown = {}
    app.f_seam.pack = lambda *a, **k: shown.__setitem__("seam", True)
    app.f_seam.pack_forget = lambda: shown.__setitem__("seam", False)
    assert app.v_seam.get() is False                     # off at the start
    for mode, on in (("inpaint", True), ("remove", True), ("outpaint", True), ("edit", False), ("txt2img", False)):
        ra.go(app, "qwen", mode)
        assert shown.get("seam") is on, (mode, shown)
        app.v_seam.set(True)
        assert app._request().seam is on, mode            # only where a new area meets the old picture
    app.reset_settings()
    assert app.v_seam.get() is False
    # per model (user 29.10.): Fibo always on without the checkbox, Flux 2 / 3 off without it, Qwen keeps it
    assert {m.key: m.seam for m in models.MODELS if m.key in ("qwen", "flux2", "flux3", "fibo")} ==         {"qwen": "switch", "flux2": "off", "flux3": "off", "fibo": "on"}
    for key, mode, box, ab, fixed in (("fibo", "inpaint", False, False, True), ("fibo", "remove", False, False, True),
                                      ("fibo", "outpaint", False, False, True), ("fibo", "edit", False, False, False),
                                      ("flux2", "outpaint", False, False, False), ("flux3", "remove", False, False, False),
                                      ("qwen", "outpaint", True, True, False)):
        ra.go(app, key, mode)
        app.v_seam.set(True)
        assert shown.get("seam", False) is box, (key, mode, shown)
        req = app._request()
        assert (req.seam, req.seam_fixed) == (ab, fixed), (key, mode, req.seam, req.seam_fixed)


def main():
    imaging_checks()
    bridge_checks()
    gui_checks()
    print("ALL OK (seam correction)")


if __name__ == "__main__":
    main()
