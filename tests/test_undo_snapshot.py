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
    """Fake PhotoCraft: new-snapshot answers with an id, select/delete want {"snapshot": id}."""
    def __init__(self, answer=lambda n: {"id": n}):
        self.calls, self.active, self.answer, self.n = [], None, answer, 0

    def connect(self):
        return self

    def session(self):
        return {"documents": [{"index": 0, "name": "a.png"}, {"index": 1, "name": "b.png"}]}

    def activate(self, i):
        self.active = i

    def execute(self, cmd, params=None):
        self.calls.append((cmd, params))
        if cmd == "history.newSnapshot":
            self.n += 1
            return self.answer(self.n)
        if cmd in ("history.selectSnapshot", "history.deleteSnapshot") and "snapshot" not in params:
            raise PhotoCraftError(f"{cmd}: `snapshot` must be a snapshot id")
        return {}


def make(pc):
    b = bridge.Bridge.__new__(bridge.Bridge)
    b.pc, b._snap, b._snap_error, b._redo = pc, None, "", None
    return b


def main():
    # nothing to undo before the first run
    try:
        make(Pc()).undo_last()
    except BridgeError as e:
        assert "Nothing to undo" in str(e)
    else:
        raise AssertionError

    # the snapshot is made, undo selects it by id in its own document; only the latest snapshot is kept
    pc = Pc(); b = make(pc)
    b._snapshot("b.png")
    b._snapshot("b.png")
    assert ("history.deleteSnapshot", {"snapshot": 1}) in pc.calls and b._snap["id"] == 2
    msg = b.undo_last()
    assert pc.active == 1 and pc.calls[-1] == ("history.selectSnapshot", {"snapshot": 2}) and "before the last AI edit" in msg

    # redo: undo keeps the state it leaves as a snapshot, redo selects it; a new run drops it
    pc = Pc(); b = make(pc)
    try:
        b.redo_last()
    except BridgeError as e:
        assert "Nothing to redo" in str(e)
    else:
        raise AssertionError
    b._snapshot("b.png")                    # id 1 = before
    b.undo_last()                           # id 2 = after, selects 1
    assert b._redo["id"] == 2 and pc.calls[-1] == ("history.selectSnapshot", {"snapshot": 1})
    msg = b.redo_last()
    assert pc.calls[-1] == ("history.selectSnapshot", {"snapshot": 2}) and "Redone" in msg
    b.undo_last()                           # undo again works, redo again too
    assert b._redo["id"] == 3
    b._snapshot("b.png")                    # next run: the redo snapshot is deleted
    assert ("history.deleteSnapshot", {"snapshot": 3}) in pc.calls and b._redo is None

    # the id can come back in other shapes
    for answer, want in ((lambda n: n, 1), (lambda n: "s7", "s7"), (lambda n: {"snapshot": {"id": 9}}, 9)):
        pc = Pc(answer); b = make(pc)
        b._snapshot("a.png")
        assert b._snap["id"] == want, (b._snap, want)

    # no id in the answer: remembered with the answer, and said when undo is asked
    pc = Pc(lambda n: {"ok": True}); b = make(pc)
    b._snapshot("a.png")
    assert b._snap is None and "gave no id" in b._snap_error
    try:
        b.undo_last()
    except BridgeError as e:
        assert "No snapshot could be made" in str(e) and "gave no id" in str(e)
    else:
        raise AssertionError
    print("ALL OK (undo snapshot)")


main()
