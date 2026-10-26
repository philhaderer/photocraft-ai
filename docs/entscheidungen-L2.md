# Entscheidungen Lane L2 (Multi Image Edit)

Technische Entscheidungen, die ich selbst getroffen habe. Jeweils: was gewählt ist, die Alternativen, und was zu tun ist, um umzudrehen.
Stand: 2026-10-26, Branch `feat/l2-multi-image`.

## 1. Wie ein Workflow seine Referenz-Slots kennzeichnet
- **Gewählt:** Feld `pc_slot` (Nummer) im `_meta` jedes Knotens eines Slots; das LoadImage trägt zusätzlich den Titel `pc:ref`. Ein Knoten in einer Kette (Flux 2: ReferenceLatent) hat `pc_pass` = Name des Eingangs, der durchgereicht wird, wenn der Slot leer bleibt. Knoten ohne `pc_slot`, aber mit `pc:ref`, zählen als Slot 1 (alte Workflows laufen unverändert).
- **Alternativen:** (a) Titel `pc:ref2`, `pc:ref3` (der Titel-Parser kennt nur Buchstaben, müsste geändert werden); (b) je Slotzahl ein eigener Workflow (`flux2-klein-edit-3refs.json`), mehr Dateien, aber jeder Workflow bleibt einfach.
- **Umdrehen:** `workflows.slot_of`, `drop_ref_slot` und die vier Workflow-Dateien ändern.

## 2. Wie ein Modell seine Bildnamen beschreibt
- **Gewählt:** `Model.tag_style` ist ein Textmuster mit `{n}` (zählt ab 1, das Bild im Dokument ist Bild 1) und `{i}` (zählt ab 0). Qwen `<image{n}>`, Fibo `<image_{n}>`, Flux 2 `image {n}`, Flux 3 `<ref_image_{i}>`.
- **Alternative:** feste Stil-Namen ("angle", "plain") mit Code je Stil. Das Muster ist kürzer und braucht keinen Code für ein neues Modell.
- **Offen:** Flux 2 `image {n}` ist eine Annahme, noch nicht live getestet.

## 3. Wo die Referenzbilder in der Anfrage liegen
- **Gewählt:** `Request.refs` = Liste von PIL-Bildern, so wie sie im Slot liegen. Die Bridge macht sie sendefertig (`refslots.prepare_image`: flach auf Weiß, höchstens 1024 px, Raster des Modells).
- **Alternative:** Das Fenster bereitet die Bilder vor. Dann müsste das Fenster das Raster der Workflows kennen.

## 4. Transparenz im Referenzbild
- **Gewählt:** Durchsichtige Stellen werden vor dem Senden weiß (`DEFAULT_BACKGROUND`). Der Wert steht an einer Stelle.
- **Alternative:** neutrales Grau (deine Vermutung bei Reference). Ob das besser ist, siehst du im Ergebnis: siehe FRAGEN.md.

## 5. Freistellen (BiRefNet) und Beschreiben (Qwen 3.5 9B) sind eigene kleine Workflows
- **Gewählt:** `workflows/birefnet-remove-bg.json` und `workflows/describe-image.json`, aufgerufen über `Bridge.remove_background(bild)` und `Bridge.describe_image(bild)`. Beide brauchen kein PhotoCraft.
- **Alternativen:** (a) Freistellen als Modus im Registry (`models.py`), dann wäre es ein Knopf im Fenster wie Edit und Fill, aber ohne Modell, zu dem es passt; (b) die Beschreibung über den Textschreiber des Fibo-Workflows.
- BiRefNet nutzt die eingebauten ComfyUI-Knoten (`LoadBackgroundRemovalModel`, `RemoveBackground`), die Maske wird vor `JoinImageWithAlpha` umgedreht (Vordergrund = 1). Live geprüft.

## 6. Wie das Slot-Fenster in `gui.py` hängt
- **Gewählt:** `RefSlotsMixin` steht in der Klassenzeile von `App` ganz vorn (die eine Hook-Zeile, plus eine Importzeile). Er umhüllt nur `_on_mode_ui` und `_request` (mit `super()`) und baut seinen Rahmen erst beim ersten Bedarf. So ändert niemand `_build`.
- **Alternative:** eine Zeile am Ende von `_build`. Das ist direkter, aber die Datei wird dann auch von anderen Lanes angefasst.
- Der Test `test_phase0.py` erlaubt genau diese zwei überschriebenen Methoden.

## 7. Referenzbilder werden nicht gespeichert
- **Gewählt:** Die Bilder leben nur im Fenster (im Speicher). Sie stehen nicht in `state.json` und nicht in Presets. Beim Wechsel des Modell-Tabs bleiben sie erhalten; was über das Limit des Modells hinausgeht, wird behalten, aber nicht gesendet.
- **Alternative:** Bilder als Dateien im Ordner `data/` speichern und beim Start laden.

## 8. Strg+V
- **Gewählt:** Strg+V fügt ein Bild ein, außer ein Textfeld hat den Fokus (Prompt, Zahlenfelder). Dort bleibt Text-Einfügen.
- **Alternative:** Strg+V nur, wenn der Mauszeiger über den Slots ist.

## 9. Reference-Modus
- **Gewählt:** Nur aus den Tabs (`models.py`) entfernt. Der Code in `bridge.py` und der Radio-Knopf im Fenster bleiben vorerst (das Fenster liest die Felder `ref_style`, `ref_collage`, `ref_cutout`).
- **Alternative:** alles auf einmal löschen. Das berührt `gui_common.py`, `gui_modes.py`, `gui_state.py` (andere Lane), siehe FRAGEN.md.

## 10. Kleinkram
- Commit-Titel beginnen mit `L2:` (statt "Window round N"), weil es keine Fenster-Runde ist.
- `tests/test_removebg.py` heißt jetzt `tests/test_slot_tools.py` (Freistellen und Beschreiben zusammen).
- Der Tk-Stub in `tests/test_gui_presets.py` kennt jetzt Frame, Label und Canvas.
- `tests/live_dnd.py` prüft tkinterdnd2 in einem Temp-Ordner, nicht in deinem Python.
- Git kann hier keine Lock-Dateien löschen: ich benenne sie in `.git/stale-*` um.
