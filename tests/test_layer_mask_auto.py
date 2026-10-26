"""Layer mask "auto": no layer mask for a Fill with a Fibo-type editor (ignores the mask), soft otherwise.

    python tests/test_layer_mask_auto.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge  # noqa: E402

eff = bridge.effective_layer_mask


def main():
    # auto: Fill / Expand / reference + editor that ignores the mask -> none; mask workflows keep soft
    assert eff("auto", "inpaint", True, True) == "none"
    assert eff("auto", "outpaint", True, True) == "none"   # Fibo redraws the whole crop: no layer mask to switch off by hand
    assert eff("auto", "outpaint", False, True) == "soft"
    assert eff("auto", "inpaint", False, True) == "soft"
    assert eff("auto", "img2img", True, True) == "soft"
    # no selection: never a layer mask, whatever was chosen
    for choice in bridge.LAYER_MASKS:
        assert eff(choice, "img2img", True, False) == "none", choice
    # an explicit choice always wins
    for choice in ("soft", "selection", "none"):
        for mode in ("inpaint", "outpaint"):
            for editor in (True, False):
                assert eff(choice, mode, editor, True) == choice, (choice, mode, editor)
    # every Fibo workflow really is an editor that ignores the mask
    for f in sorted((ROOT / "workflows").glob("fibo2-edit-*.json")):
        if f.name.endswith(".group.json"):
            continue
        assert not bridge.mask_is_used(json.loads(f.read_text(encoding="utf-8"))), f.name
    # default of the request and of the CLI
    assert bridge.Request().layer_mask == "auto"
    print("ALL OK (layer mask auto)")


if __name__ == "__main__":
    main()
