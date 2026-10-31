"""The "LLM" button left of the bin beside "Prompt" (user 30.10.): the text model of the chosen model describes the picture in
PhotoCraft and the text goes to the end of the prompt after a line break (an empty prompt: just the text). The model's own
writer first, then Qwen 3.5 9B int8 ConvRot; no file, no function or the Remove prompt switched off: grey. Stubbed Tk,
PhotoCraft and ComfyUI.

    python tests/test_llm_button.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
import test_reference_mode as t  # noqa: E402

from pccomfy import manifest, models  # noqa: E402


class Inv:
    def __init__(self, have):
        self.have = set(have)

    def found(self, name):
        return name if name in self.have else None


def manifest_checks():
    assert manifest.describe_writers("fibo") == ("qwen3.5_9b_int8_convrot.safetensors",)
    assert manifest.describe_writers("krea2") == ("qwen3vl_4b_fp8_scaled.safetensors", "qwen3.5_9b_int8_convrot.safetensors")
    for m in models.MODELS:
        names = manifest.describe_writers(m.key)
        assert names and names[-1] == "qwen3.5_9b_int8_convrot.safetensors", m.key
        assert all(n in manifest.FILES for n in names), (m.key, names)


def settings_checks():
    # the fallback is listed (optional) in every model's tab, so it can be downloaded from any of them
    assert set(manifest.used_by(manifest.DESCRIBE_FALLBACK)) == set(manifest.TABS), manifest.used_by(manifest.DESCRIBE_FALLBACK)
    have = lambda n: n != "qwen3.5_9b_w4a8_gptq.safetensors"  # noqa: E731
    line = manifest.describe_line("qwen", have)
    assert "Qwen 3.5 9B w4a8 GPTQ (missing)" in line and "Fallback when it is missing: Qwen 3.5 9B int8 ConvRot." in line, line
    assert "Multi Image Edit" in line
    fibo = manifest.describe_line("fibo", lambda n: True)
    assert "Qwen 3.5 9B int8 ConvRot." in fibo and "fallback for the other models" in fibo and "missing" not in fibo.replace("is missing", ""), fibo


def bridge_checks():
    pc, _, b = t.make(tempfile.mkdtemp(), layers=2)
    asked = []
    b.describe_image = lambda im, progress=None, question="", clip="", **kw: asked.append((im.size, question, clip)) or "two people"
    assert b.describe_canvas("qwen3.5_9b_w4a8_gptq.safetensors") == "two people"
    (size, question, clip), = asked
    assert size == (t.W, t.H) and question == "" and clip == "qwen3.5_9b_w4a8_gptq.safetensors", asked


def run(app, pending):
    for _ in range(50):
        if not pending:
            break
        time.sleep(0.02)
        pending.pop(0)()


def gui_checks():
    app = ra.make()
    ra.go(app, "qwen", "edit")
    # which file: the model's own, else the fallback, else none
    app.inv = Inv({"qwen3.5_9b_w4a8_gptq.safetensors", "qwen3.5_9b_int8_convrot.safetensors"})
    assert app._llm_file() == "qwen3.5_9b_w4a8_gptq.safetensors"
    app.inv = Inv({"qwen3.5_9b_int8_convrot.safetensors"})
    assert app._llm_file() == "qwen3.5_9b_int8_convrot.safetensors"
    app._update_llm_button()
    assert app.b_llm["state"] == "normal"
    app.inv = Inv(set())
    assert app._llm_file() == ""
    app._update_llm_button()
    assert app.b_llm["state"] == "disabled" and "qwen3.5_9b_w4a8_gptq.safetensors" in app.tt_llm.text
    app.inv = Inv({"qwen3.5_9b_int8_convrot.safetensors"})
    app._update_llm_button()
    assert app.b_llm["state"] == "normal"

    # the text is added after a line break; an empty prompt gets the text alone
    pending = []
    app.root.after = lambda ms, fn=None, *a: pending.append(fn)
    got = []
    app.bridge.describe_canvas = lambda clip="", progress=None: got.append(clip) or "a quiet harbour at dusk"
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "make it night")
    app.describe_canvas()
    run(app, pending)
    assert got == ["qwen3.5_9b_int8_convrot.safetensors"]
    assert app.t_prompt.get("1.0", "end").strip() == "make it night\na quiet harbour at dusk"
    assert "Described" in app.v_status.get() and app.b_llm["state"] == "normal"
    app.t_prompt.delete("1.0", "end")
    app.describe_canvas()
    run(app, pending)
    assert app.t_prompt.get("1.0", "end").strip() == "a quiet harbour at dusk"
    # a failure is shown, the prompt stays
    app.bridge.describe_canvas = lambda clip="", progress=None: (_ for _ in ()).throw(RuntimeError("ComfyUI is not running"))
    app.describe_canvas()
    run(app, pending)
    assert "Describe failed" in app.v_status.get() and "harbour" in app.t_prompt.get("1.0", "end")


def relink_checks():
    """A text model the user linked to another file (settings, chain symbol; user 1.11.): the LLM button uses the linked file
    and its graph loads it; a link whose file is gone falls back to the expected file, and with neither the button is grey."""
    from pccomfy import inventory, workflows
    fb, mine = manifest.DESCRIBE_FALLBACK, "mine\other-llm.safetensors"
    app = ra.make()
    ra.go(app, "fibo", "edit")
    app.inv = inventory.Inventory({"clip": [fb, mine]}, mapping={fb: mine})
    assert app._llm_file() == mine
    g, _ = workflows.apply_template(workflows.load_template(workflows.DESCRIBE_WORKFLOW), workflows.GenParams(clip=app._llm_file()), "x.png", None)
    assert [n["inputs"]["clip_name"] for n in g.values() if n["class_type"] == "CLIPLoader"] == [mine]
    app.inv = inventory.Inventory({"clip": [fb]}, mapping={fb: mine})          # the linked file was removed
    assert app._llm_file() == fb
    app._update_llm_button()
    assert app.b_llm["state"] == "normal"
    app.inv = inventory.Inventory({"clip": []}, mapping={fb: mine})            # nothing left
    app._update_llm_button()
    assert app._llm_file() == "" and app.b_llm["state"] == "disabled"


def main():
    relink_checks()
    manifest_checks()
    bridge_checks()
    gui_checks()
    print("ALL OK (llm button)")


if __name__ == "__main__":
    main()
