"""The icon beside the seed field puts the seed of the last finished run back (user 1.11.). Stubbed Tk.

    python tests/test_last_seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)


def main():
    app = ra.make()
    assert app.b_last_seed["state"] == "disabled" and app._last_seed is None
    app.use_last_seed()                                   # nothing to repeat yet
    assert app.v_seed.get() == -1
    app._set_last_seed(None)
    app._set_last_seed("x")
    assert app._last_seed is None and app.b_last_seed["state"] == "disabled"
    app._set_last_seed(12345678)
    assert app.b_last_seed["state"] == "normal"
    app.use_last_seed()
    assert app.v_seed.get() == 12345678
    print("ALL OK (last seed)")


if __name__ == "__main__":
    main()
