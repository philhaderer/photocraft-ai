"""Builds pccomfy/assets/styles.json (the style prompts of the Styles button) from the chosen selection.

    python tools/build_styles.py [data/styles/auswahl-final.json [data/styles/krea_moodboards.json]]

The selection (groups with an `index` and a short name per style) and the text source (`krea_moodboards.json` of ThetaCursed/Krea2-Style-Explorer,
MIT, https://github.com/ThetaCursed/Krea2-Style-Explorer) live in data/styles (git-ignored). The texts are copied character for character
(`styleKeywords`); only the group and the short name come from the selection. Today only Text to image gets styles.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = "txt2img"


def build(selection: Path, source: Path) -> dict:
    texts = {e["index"]: e["styleKeywords"] for e in json.loads(source.read_text(encoding="utf-8"))}
    groups = []
    for g in json.loads(selection.read_text(encoding="utf-8"))["groups"]:
        groups.append({"name": g["name"], "styles": [{"name": s["name"], "text": texts[s["index"]]} for s in g["styles"]]})
    return {
        "source": "ThetaCursed/Krea2-Style-Explorer, krea_moodboards.json, styleKeywords (MIT, see LICENSE-krea-style-explorer.txt)",
        "modes": {MODE: {"groups": groups}},
    }


def main(argv: list[str]) -> int:
    sel = Path(argv[0]) if argv else ROOT / "data" / "styles" / "auswahl-final.json"
    src = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "styles" / "krea_moodboards.json"
    out = ROOT / "pccomfy" / "assets" / "styles.json"
    data = build(sel, src)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(g["styles"]) for g in data["modes"][MODE]["groups"])
    print(f"{out}: {n} styles in {len(data['modes'][MODE]['groups'])} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
