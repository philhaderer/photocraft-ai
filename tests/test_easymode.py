"""Easy Mode core (no window): the six functions, the priority, the best installed model, the saved switch.

    python tests/test_easymode.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="pccomfy-easy-")
os.environ["PCCOMFY_HOME"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pccomfy import easymode as em  # noqa: E402
from pccomfy import models  # noqa: E402


def main():
    assert em.EASY_MODES == ("txt2img", "edit", "inpaint", "remove", "outpaint", "upscale")
    assert "multi_edit" not in em.EASY_MODES and "refine" not in em.EASY_MODES
    # every key in the priority is a model that really has the function
    for mode, keys in em.PRIORITY.items():
        assert mode in em.EASY_MODES
        for k in keys:
            assert mode in models.BY_KEY[k].modes, (mode, k)
    assert set(em.PRIORITY) == set(em.EASY_MODES)
    for mode, keys in em.EXTRA_PRIORITY.items():             # the functions Easy Mode leaves out: only models that really have them
        assert mode not in em.EASY_MODES and all(mode in models.BY_KEY[k].modes for k in keys)

    everything = lambda k: True  # noqa: E731
    assert em.available_modes(everything) == {
        "txt2img": "flux3", "edit": "flux3", "inpaint": "fibo", "remove": "fibo", "outpaint": "flux2", "upscale": "flux3"}

    # the starter models Fibo + Flux 3 cover all six functions
    starter = lambda k: k in em.STARTER_MODELS  # noqa: E731
    got = em.available_modes(starter)
    assert all(got.values()), got
    assert got["outpaint"] == "flux3" and got["inpaint"] == "fibo"

    # Flux 3 locked as a whole: the next model takes over; Upscale has no other model offered here -> greyed out
    no_flux3 = lambda k: k == "fibo"  # noqa: E731
    got = em.available_modes(no_flux3)
    assert got["txt2img"] == "fibo" and got["edit"] == "fibo" and got["outpaint"] == "fibo" and got["upscale"] == ""

    # hidden models are never chosen
    assert em.best_model("inpaint", everything, hidden={"fibo"}) == "qwen"
    assert em.best_model("inpaint", everything, hidden={"fibo", "qwen"}) == ""
    assert em.best_model("refine", everything) == ""          # not an Easy Mode function
    assert em.available_modes(lambda k: False) == {m: "" for m in em.EASY_MODES}

    assert em.model_line("fibo") == models.BY_KEY["fibo"].label
    assert em.model_line("") == "" and em.model_line("nope") == ""

    # the switch and the kept state live in settings.json
    assert em.is_on() is False
    em.set_on(True)
    assert em.is_on() is True
    em.set_on(False)
    assert em.is_on() is False
    em.save_return({"model": "qwen", "mode": "edit"})
    assert em.pop_return() == {"model": "qwen", "mode": "edit"}
    assert em.pop_return() == {}

    shutil.rmtree(TMP, ignore_errors=True)
    print("ALL OK (easy mode core)")


if __name__ == "__main__":
    main()
