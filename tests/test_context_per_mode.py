"""Context is remembered per mode; Generative fill starts at 0.2, the other modes keep the default.

    python tests/test_context_per_mode.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def main():
    app = gui.App(cfgmod.load())
    app.v_model.set(""); app.v_workflow.set("my_own_workflow.json")   # a workflow of your own: no model sets the context
    app.v_mode.set("inpaint"); app._on_mode()
    app.v_context.set(0.3)                                   # the user changes it in Generative fill
    app.v_mode.set("remove"); app._on_mode()
    assert app.v_context.get() == app._ctx_default           # other modes: the default
    app.v_context.set(0.6)
    app.v_mode.set("inpaint"); app._on_mode()
    assert app.v_context.get() == 0.3                        # fill got its own value back
    app.v_mode.set("remove"); app._on_mode()
    assert app.v_context.get() == 0.6
    fresh = gui.App(cfgmod.load())
    assert fresh._ctx["inpaint"] == gui.FILL_CONTEXT == 0.2
    print("ALL OK (context per mode)")


main()
