"""Runs every tests/test_*.py in its own Python process and prints one line per file and a summary.
Run: python tests/run_all.py            (all files)
     python tests/run_all.py bars round  (only files whose name contains one of the words)
Exit code 0 = all green. The tests use a stubbed Tk and a fake PhotoCraft: the real window and real generations are not covered."""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main(words: list[str]) -> int:
    files = sorted(p for p in HERE.glob("test_*.py") if not words or any(w in p.name for w in words))
    if not files:
        print("No test file matches:", " ".join(words))
        return 2
    failed = []
    t_all = time.monotonic()
    for p in files:
        t0 = time.monotonic()
        try:
            r = subprocess.run([sys.executable, "-B", str(p)], cwd=ROOT, capture_output=True, text=True, timeout=300)
            ok, out = r.returncode == 0, (r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            ok, out = False, "timeout after 300 s"
        print(f"{'ok  ' if ok else 'FAIL'} {p.name:<34} {time.monotonic() - t0:5.1f} s")
        if not ok:
            failed.append(p.name)
            print("     " + "\n     ".join(out.strip().splitlines()[-12:]))
    print(f"\n{len(files) - len(failed)} of {len(files)} test files green in {time.monotonic() - t_all:.0f} s"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
