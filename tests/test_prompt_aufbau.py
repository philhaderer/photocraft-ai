"""The total prompt of Multi Image Edit per model, produced by the real functions (the slots, the window's prompt joining,
the bridge, the workflow). Prints the four examples; with --write it writes docs/prompt-aufbau.md from them.

    python tests/test_prompt_aufbau.py [--write]
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from pccomfy import models, refslots, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
import test_reference_mode as T  # noqa: E402

WF = {"qwen": "qwen-image-21-edit.json", "fibo": "fibo2-edit.json", "flux2": "flux2-klein-edit.json", "flux3": "flux3-klein-edit.json"}
DESCRIPTIONS = ["A brown dog with a red collar, sitting on grass.", "A blue knitted hat with a white pompom."]


def example(key: str) -> dict:
    """What really reaches the text encoder for this model: two reference images, both described, and a typed text."""
    m = models.BY_KEY[key]
    rs = refslots.RefSlots()
    rs.set_model(m.max_refs, m.tag_style)
    for i, d in enumerate(DESCRIPTIONS[:m.max_refs]):
        rs.add(Image.new("RGB", (64, 64), "red"), f"r{i}.png")
        rs.items[-1].description = d
    typed = f"Put the hat from {rs.tag(1)} on the dog from {rs.tag(0)}."
    window_prompt = rs.prompt_with_descriptions(typed)          # what the window puts into the request
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / WF[key]), enhance=False, preset="X", run_no=1, refs=rs.images())
    req.params = workflows.GenParams(prompt=window_prompt, seed=3)
    b.run(req)
    g = b.comfy.graphs[0]
    sent = next(v for n in g.values() for k, v in n.get("inputs", {}).items()
                if k in ("prompt", "text") and isinstance(v, str) and typed in v)      # the text field of the encoder
    return {"model": m.label, "key": key, "tags": [rs.picture_tag()] + [rs.tag(k) for k in range(len(rs.active))],
            "typed": typed, "window": window_prompt, "sent": sent}


def main():
    out = [example(k) for k in WF]
    for e in out:
        assert e["sent"] and DESCRIPTIONS[0] in e["sent"] and DESCRIPTIONS[1] in e["sent"] and e["typed"] in e["sent"], e
        print(f"--- {e['model']}  (tags: picture {e['tags'][0]}, references {', '.join(e['tags'][1:])})\n{e['sent']}\n")
    if "--write" in sys.argv:
        parts = ["# Der gesendete Prompt bei „Multi Image Edit“\n",
                 "Diese Datei wird von `python tests/test_prompt_aufbau.py --write` erzeugt: Die Beispiele sind die echte Ausgabe der "
                 "echten Funktionen (Slots, Fenster, Bridge, Workflow), kein von Hand geschriebener Text.\n",
                 "## Aufbau\n",
                 "1. Das Bild im PhotoCraft-Dokument ist immer „Bild 1“. Die Referenzbilder sind Bild 2, 3 … (Reihenfolge der Slots).",
                 "2. Du tippst deinen Text und nennst die Bilder mit ihren Namen (unter den Slots steht, wie sie heißen).",
                 "3. Hat ein Referenzbild eine Beschreibung, wird sie automatisch ans Ende deines Textes gehängt, eine Zeile pro Bild: `<Name>: <Beschreibung>`.",
                 "4. Der Workflow setzt den Namen des Hauptbildes vorn davor, wenn das Modell einen braucht (`pc_image_tag`).",
                 "5. Das Textfeld im Fenster bleibt unverändert; das Anhängen passiert erst beim Senden.\n",
                 "Beispiel in allen vier Fällen: zwei Referenzbilder (Hund, Mütze), beide beschrieben.\n"]
        for e in out:
            parts += [f"## {e['model']}\n",
                      f"Namen: Bild = `{e['tags'][0]}`, Referenzen = " + ", ".join(f"`{t}`" for t in e["tags"][1:]) + "\n",
                      "Dein Text:\n", "```", e["typed"], "```\n", "Gesendet an den Text-Encoder:\n", "```", e["sent"], "```\n"]
        parts += ["## Sieht man den gesendeten Prompt im Betrieb?\n",
                  "`data/exchange/runs.jsonl` hat pro Lauf eine Zeile mit dem Prompt (Feld `prompt`). Das ist dein Text plus die angehängten "
                  "Beschreibungen, aber ohne den Bildnamen, den der Workflow davorsetzt, und bei langen Texten nach 600 Zeichen abgeschnitten. "
                  "Der Text, der wirklich beim Encoder ankommt, steht in `data/exchange/last-graph.json` (nur der letzte Lauf). "
                  "Für den Alltag reicht `runs.jsonl`; für die Frage „was genau sah das Modell?“ nimm `last-graph.json`.\n"]
        (ROOT / "docs" / "prompt-aufbau.md").write_text("\n".join(parts), encoding="utf-8")
        print("written: docs/prompt-aufbau.md")
    print("ALL OK (prompt structure)")


if __name__ == "__main__":
    main()
