"""Right-click menu on the model chips (L3, user 29.10.): favourite of the chosen function (a tick in the menu) and "Hide
this model". A hidden chip leaves the row, the others close up; hiding the chosen model chooses another one; the favourite
comes first when a function picks its model; a function whose models are all hidden is greyed out.

    python tests/test_model_chip_menu.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
models = gui.models


class Menu:
    def __init__(self):
        self.items = []

    def delete(self, *a):
        self.items = []

    def add_checkbutton(self, **k):
        self.items.append(("check", k))

    def add_command(self, **k):
        self.items.append(("command", k))

    def add_separator(self):
        self.items.append(("sep", {}))

    def tk_popup(self, *a):
        pass

    def grab_release(self):
        pass


class Ev:
    x_root = y_root = 10


def chips(app):
    """The chips in the row: key -> (row, column); a hidden one is not there."""
    out = {}
    for key, rb in app.rb_tabs.items():
        g = rb.__dict__.get("_grid")
        if g is not None:
            out[key] = g
    return out


def main():
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    for rb in app.rb_tabs.values():                       # record grid / grid_remove of each chip
        rb.grid = lambda *a, w=rb, **k: w.__dict__.__setitem__("_grid", (k["row"], k["column"]))
        rb.grid_remove = lambda w=rb: w.__dict__.pop("_grid", None)
    for rb in app.rb_modes.values():
        rb.grid = lambda *a, **k: None
    app.m_chip = Menu()
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    app._update_mode_radios()
    assert len(chips(app)) == len(models.MODELS), chips(app)

    # the menu: favourite for the chosen function (ticked when it is the favourite), hide
    app._chip_menu("fibo", Ev())
    assert [(kind, it.get("label")) for kind, it in app.m_chip.items] == [
        ("command", "Set as my settings for this mode and model"), ("sep", None),
        ("check", "Favourite for Fill Selection"), ("command", "Hide this model")]
    fav = app.m_chip.items[2][1]
    assert fav["state"] == "normal" and app.m_chip.items[0][1]["state"] == "disabled"      # Fibo is not the chosen model: no saving
    assert app.v_chip_fav.get() is False
    app.v_chip_fav.set(True)
    fav["command"]()
    assert cfgmod.favorites() == {"inpaint": "fibo"}
    app._chip_menu("fibo", Ev())
    assert app.v_chip_fav.get() is True                   # ticked now
    app._chip_menu("flux3", Ev())                         # Flux 3 cannot fill: no favourite for it
    assert app.m_chip.items[2][1]["state"] == "disabled" and app.v_chip_fav.get() is False

    # the favourite comes before the model last used when the function picks its model
    app._mode_model["inpaint"] = "qwen"
    assert app._model_for_mode("inpaint") == "fibo"
    app._chip_menu("fibo", Ev())
    app.v_chip_fav.set(False)                             # untick (Tk flips the variable, then runs the command)
    app.m_chip.items[2][1]["command"]()
    assert cfgmod.favorites() == {} and app._model_for_mode("inpaint") == "qwen"

    # hide a chip that is not chosen: it leaves the row, the others close up
    app._set_model_hidden("flux2", True)
    assert cfgmod.hidden_tabs() == {"flux2"} and "flux2" not in chips(app)
    order = [m.key for m in models.MODELS if m.key != "flux2"]
    assert [k for k, _ in sorted(chips(app).items(), key=lambda kv: kv[1])] == order
    assert chips(app)[order[1]] == (0, 1) and chips(app)[order[3]] == (1, 0)
    assert app.v_model.get() == "qwen"

    # hide the chosen model: another one that can fill is chosen, the function stays
    app._set_model_hidden("qwen", True)
    assert app.v_model.get() == "fibo" and app.v_mode.get() == "inpaint", (app.v_model.get(), app.v_mode.get())
    assert app._model_for_mode("inpaint") == "fibo"

    # every model that can fill hidden: Fill is greyed out, the chosen model goes to one still shown
    app._set_model_hidden("fibo", True)
    left = [m for m in models.MODELS if m.key not in cfgmod.hidden_tabs()]
    if not any("inpaint" in m.modes for m in left):
        assert app.rb_modes["inpaint"].cget("state") == "disabled"
        assert app._model_for_mode("inpaint") == ""
    assert app.v_model.get() in {m.key for m in left}

    # shown again (the gear window): back in its place, the function too
    for k in ("flux2", "qwen", "fibo"):
        app._set_model_hidden(k, False)
    assert cfgmod.hidden_tabs() == set() and len(chips(app)) == len(models.MODELS)
    assert app.rb_modes["inpaint"].cget("state") == "normal"

    # the gear window, tab "Models": one tick per model, all ticked after installing; unticking hides, ticking shows
    app._fill_text = lambda *a: None                      # (the stub Text has no tags)
    app.open_settings()
    assert list(app._shown_vars) == [m.key for m in models.MODELS] and all(v.get() for v in app._shown_vars.values())
    app._shown_vars["krea2"].set(False)
    app._set_model_hidden("krea2", not app._shown_vars["krea2"].get())     # what the tick's command does
    assert cfgmod.hidden_tabs() == {"krea2"} and "krea2" not in chips(app)
    app._set_model_hidden("moss", True)                   # the right-click menu: the gear window follows
    assert app._shown_vars["moss"].get() is False
    app._shown_vars["krea2"].set(True)
    app._set_model_hidden("krea2", False)
    app._set_model_hidden("moss", False)
    assert cfgmod.hidden_tabs() == set() and all(v.get() for v in app._shown_vars.values())
    app._settings_close()

    # every model hidden: none is chosen
    for m in models.MODELS:
        app._set_model_hidden(m.key, True)
    assert app.v_model.get() == "" and chips(app) == {}
    for m in models.MODELS:
        app._set_model_hidden(m.key, False)
    print("test_model_chip_menu: ok")


if __name__ == "__main__":
    main()
