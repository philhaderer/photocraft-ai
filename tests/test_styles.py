"""The Styles button beside the prompt (user 1.11.): styles.json (186 style prompts of the Krea 2 Style Explorer, MIT, in 9 groups,
Text to image only), the loader (a broken file means no styles), the palette icon, the button (only in a mode that has styles,
not in Easy Mode), a click on an entry is ADDED to the prompt after a line break, and the whole text of every entry is kept for the hover box.
Stubbed Tk.

    python tests/test_styles.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

from pccomfy import icons, styles  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def data_checks():
    got = styles.load()
    assert list(got) == ["txt2img"], list(got)       # only Text to image so far; another mode needs only its own key
    groups = got["txt2img"]
    assert len(groups) == 9 and sum(len(g["styles"]) for g in groups) == 186
    names = [s["name"] for g in groups for s in g["styles"]]
    assert len(set(names)) == len(names), "short names must be unique"
    assert all(s["text"].strip() and s["name"].strip() for g in groups for s in g["styles"])
    assert all(len(g["styles"]) <= 25 for g in groups)       # a menu that fits the screen
    assert (ROOT / "pccomfy" / "assets" / "LICENSE-krea-style-explorer.txt").read_text(encoding="utf-8").startswith("Style texts")
    # the texts are the source's, character for character (the source lives in data/, not in the repo: only checked where it is)
    src = ROOT / "data" / "styles" / "krea_moodboards.json"
    sel = ROOT / "data" / "styles" / "auswahl-final.json"
    if src.exists() and sel.exists():
        texts = {e["index"]: e["styleKeywords"] for e in json.loads(src.read_text(encoding="utf-8"))}
        want = [(g["name"], s["name"], texts[s["index"]]) for g in json.loads(sel.read_text(encoding="utf-8"))["groups"] for s in g["styles"]]
        have = [(g["name"], s["name"], s["text"]) for g in groups for s in g["styles"]]
        assert have == want
    else:
        print("  (source files not in data/styles: texts not compared)")


def loader_checks():
    d = Path(tempfile.mkdtemp())

    def write(obj, name="s.json"):
        p = d / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
        return p
    assert styles.load(d / "missing.json") == {}
    assert styles.load(write("{not json")) == {}
    assert styles.load(write({"modes": []})) == {}
    assert styles.load(write({"x": 1})) == {}
    ok = styles.load(write({"modes": {
        "txt2img": {"groups": [{"name": "A", "styles": [{"name": "one", "text": "t1"}, {"name": "", "text": "x"}, {"name": "bad"}, 5]},
                               {"name": "empty", "styles": []}, {"name": " ", "styles": [{"name": "n", "text": "t"}]}]},
        "edit": {"groups": [{"name": "B", "styles": [{"name": "two", "text": "t2"}]}]},
        "broken": 7}}))
    assert ok == {"txt2img": [{"name": "A", "styles": [{"name": "one", "text": "t1"}]}],
                  "edit": [{"name": "B", "styles": [{"name": "two", "text": "t2"}]}]}, ok


def icon_checks():
    assert "palette" in icons.SHAPES
    im = icons.render("palette", "#ffffff", 40)
    assert im.size == (40, 40) and im.getchannel("A").getextrema()[1] == 255


def gui_checks():
    app = ra.make()
    assert set(app.m_styles) == {"txt2img"} and len(app._style_texts) == 186
    # the button: only in Text to image, not in Easy Mode
    ra.go(app, "flux3", "txt2img")
    app._on_mode_ui()
    assert app._styles_shown
    ra.go(app, "flux3", "edit")
    app._on_mode_ui()
    assert not app._styles_shown
    ra.go(app, "flux3", "txt2img")
    app._on_mode_ui()
    assert app._styles_shown
    app._easy = True
    app._easy_hide()
    assert app._styles_shown                 # Easy Mode keeps the button (user 1.11.)
    app._on_mode_ui()
    assert app._styles_shown
    app._easy = False
    app._update_styles_button()
    assert app._styles_shown
    # an entry is added after a line break (an empty field just gets the style; one undo step in a real Tk)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red bicycle")
    first = styles.load()["txt2img"][0]["styles"][0]["text"]
    app._apply_style(first)
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle\n" + first
    assert "Ctrl+Z" in app.v_status.get()
    # a field that is switched off is left alone
    app.t_prompt.configure(state="disabled")
    app._apply_style("other")
    app.t_prompt.configure(state="normal")
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle\n" + first
    # the hover box: the whole text of an entry by (menu, number); nothing for a group entry or "none"
    key, text = next(iter(app._style_texts.items()))
    menu = type("M", (), {"__str__": lambda s: key[0]})()
    assert app._style_text_at(menu, key[1]) == text and text in {t for g in styles.load()["txt2img"] for t in [s["text"] for s in g["styles"]]}
    assert app._style_text_at(menu, "none") == "" and app._style_text_at(menu, None) == "" and app._style_text_at(menu, 999) == ""


def main():
    data_checks()
    loader_checks()
    icon_checks()
    gui_checks()
    print("ALL OK (styles)")


if __name__ == "__main__":
    main()
