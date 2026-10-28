"""Number fields: typing, deleting, comma or point, the unit kept while editing, Up/Down steps, LoRA strengths
(stubbed Tk, no display needed).

Live bugs 28.10.: "%", the space and "hard edge" could not be deleted (the key check also ran on deleting); a
double-click selected the unit too; LoRA strengths took letters and no comma.

    python tests/test_number_fields.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def main():
    ok = gui.number_typed_ok                 # Tk's %d (1 = insert, 0 = delete), %S, %P
    assert ok("0", "%", "4 ") and ok("0", " ", "4%") and ok("0", "hard edge", "") and ok("0", "e", "hard edg")
    assert ok("1", "5", "5") and ok("1", "3", "0.3") and ok("1", ",", "0,") and ok("1", "12", "12")
    assert not ok("1", "a", "a") and not ok("1", "%", "5%") and not ok("1", ".", "0.5.") and not ok("1", ",", "0.5,")
    assert not ok("1", "-", "-") and not ok("1", " ", "5 ")
    p = gui.parse_number
    assert p("0,2") == 0.2 and p("0.2") == 0.2 and p("35 %") == 35 and p(" 12,5 ") == 12.5 and p("abc") is None and p("") is None

    app = t.gui.App(cfgmod.load())
    # the unit stays while editing (user 28.10.: else the number shifts); a double-click or Tab selects only the number
    box = app.lbl_sharpen
    app.v_sharpen.set(0.3)
    app._on_sharpen()
    assert box.cget("text") == "30 %"
    box._start_edit()
    box._select_number()
    assert box.cget("text") == "30 %"
    span = gui.ValueBox._number_span
    assert span("30 %") == (0, 2) and span("0.45") == (0, 4) and span("12,5 %") == (0, 4) and span("hard edge") == (0, 9)
    app.w_feather.configure(state="normal")
    app.v_feather.set(0)
    app._on_feather()
    assert app.lbl_feather.cget("text") == "hard edge"
    app.lbl_feather.configure(text="hard3 edge")        # a digit typed into "hard edge"
    app.lbl_feather._commit()
    assert app.v_feather.get() == 3
    # comma or point, and a unit left in the text
    app.lbl_context.configure(text="0,2")
    app.lbl_context._commit()
    assert abs(app.v_context.get() - 0.2) < 1e-9 and app.lbl_context.cget("text") == "0.20"
    # Up/Down: 0.05 for a 0..1 value, 1 for %; from the typed value; kept in range
    app.lbl_context.configure(text="0.40")
    app.lbl_context._step(1)
    assert abs(app.v_context.get() - 0.45) < 1e-9 and app.lbl_context.cget("text") == "0.45"
    app.lbl_context._step(-1)
    app.lbl_context._step(-1)
    assert abs(app.v_context.get() - 0.35) < 1e-9
    app.v_context.set(1.0)
    app.lbl_context._step(1)
    assert app.v_context.get() == 1.0
    box.configure(text="30")
    box._step(1)
    assert abs(app.v_sharpen.get() - 0.31) < 1e-9 and box.cget("text") == "31 %"
    box._step(-1)
    box._step(-1)
    assert abs(app.v_sharpen.get() - 0.29) < 1e-9
    app.v_feather.set(4)
    app._on_feather()
    app.lbl_feather._step(1)
    assert app.v_feather.get() == 5                     # Edge feather: 1 % (user 28.10.)
    app.v_density.set(100)
    app._on_density()
    app.lbl_density._step(1)
    app.lbl_density._step(-1)
    assert app.v_density.get() == 99
    app.w_sharpen.configure(state="disabled")           # a greyed-out slider does not step
    app.v_sharpen.set(0.5)
    box._step(1)
    assert app.v_sharpen.get() == 0.5
    app.w_sharpen.configure(state="normal")

    # LoRA rows: numbers only, comma or point, kept in 0..1.5
    app._add_lora_row("a.safetensors", 0.8)
    rec = app.lora_rows[-1]
    assert rec["strength"].get() == "0.8"
    for typed, want in (("0,2", 0.2), ("0.35", 0.35), ("2", 1.5), ("abc", 1.0), ("", 1.0)):
        rec["strength"].set(typed)
        assert app._loras()[-1] == ["a.safetensors", want], (typed, app._loras())
    rec["strength"].set("0,2")
    app._lora_strength_text(rec)
    assert rec["strength"].get() == "0.2"
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (number fields)")


if __name__ == "__main__":
    main()
