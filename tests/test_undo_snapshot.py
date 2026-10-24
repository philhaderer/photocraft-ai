"""One history snapshot per run and "Undo AI edit" going back to it.

    python tests/test_undo_snapshot.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge  # noqa: E402
from pccomfy.bridge import BridgeError  # noqa: E402
from pccomfy.photocraft import PhotoCraftError  # noqa: E402


class Pc:
    def __init__(self, accept=("name",)):
        self.calls, self.accept, self.active = [], accept, None

    def connect(self):
        return self

    def session(self):
        return {"documents": [{"index": 0, "name": "a.png"}, {"index": 1, "name": "b.png"}]}

    def activate(self, i):
        self.active = i

    def execute(self, cmd, params=None):
        self.calls.append((cmd, params))
        if cmd in ("history.newSnapshot", "history.selectSnapshot") and not (set(params) & set(self.accept)):
            raise PhotoCraftError(f"{cmd}: bad params")
        return {}


def make(pc):
    b = bridge.Bridge.__new__(bridge.Bridge)
    b.pc, b._snap, b._snap_error = pc, None, ""
    return b


def main():
    # nothing to undo before the first run
    try:
        make(Pc()).undo_last()
    except BridgeError as e:
        assert "Nothing to undo" in str(e)
    else:
        raise AssertionError

    # the snapshot is made, undo selects it in its own document; only the latest snapshot is kept
    pc = Pc(); b = make(pc)
    b._snapshot("b.png")
    first = b._snap["name"]
    assert pc.calls[0][0] == "history.newSnapshot"
    b._snapshot("b.png")
    assert ("history.deleteSnapshot", {"name": first}) in pc.calls or first == b._snap["name"]
    msg = b.undo_last()
    assert pc.active == 1 and pc.calls[-1] == ("history.selectSnapshot", {"name": b._snap["name"]}) and "before the last AI edit" in msg

    # the other spelling of the parameter is found
    pc = Pc(accept=("snapshot",)); b = make(pc)
    b._snapshot("a.png")
    assert b._snap["key"] == "snapshot"
    b.undo_last()
    assert pc.calls[-1][1] == {"snapshot": b._snap["name"]}

    # no snapshot possible: remembered, and said when undo is asked
    pc = Pc(accept=()); b = make(pc)
    b._snapshot("a.png")
    assert b._snap is None and b._snap_error
    try:
        b.undo_last()
    except BridgeError as e:
        assert "No snapshot could be made" in str(e)
    else:
        raise AssertionError
    print("ALL OK (undo snapshot)")


main()
