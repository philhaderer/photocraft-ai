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

## 9. Reference-Modus (erledigt in Runde 2)
- **Erledigt:** Der Modus „Insert reference image“ ist überall entfernt (Bridge, Fenster, Zustand, Kommandozeile, Hilfsfunktionen in `imaging.py`, Tests). Alte Presets mit dem Modus fallen auf den ersten Modus des Tabs zurück.
- **Neu:** Modus `multi_edit` („Multi Image Edit“), im Modus-Block an der Stelle des alten. Er steht bei Qwen, Fibo, Flux 2 und Flux 3 und läuft als `run_as="edit"`: Edit-Workflow des Modells, ganzes Bild, keine Maske, Auswahl wird ignoriert. Die Slots erscheinen nur in diesem Modus (nicht bei Edit, Fill, Expand).
- **Technisch:** `Request.mode` ist beim Lauf `edit`; das Fenster merkt sich `multi_edit` (Zustand speichert jetzt den gewählten Modus, nicht den Lauf-Modus; das behebt nebenbei, dass „Refine“ nach einem Neustart als „Edit“ zurückkam).
- **Alternative:** Eigener Bridge-Modus `multi_edit` statt `run_as`. Mehr Code, kein Vorteil, solange er wie Edit läuft.
- **Offen (FRAGEN.md 7):** mit Auswahl arbeiten? Ergebnis als neues Dokument?
- **Manifest:** `manifest.py` (L1) kennt `multi_edit` noch nicht. Es braucht je Tab eine Zeile `"multi_edit": ModeSpec(requires=...)` wie bei `edit`; bis dahin ist `tests/test_detection.py` rot.

## 12. Hintergrund hinter freigestellten Bildern
- **Gewählt:** neutrales Grau (128, 128, 128), ein einziger Wert: `refslots.DEFAULT_BACKGROUND`. Gilt für alles, was durchsichtig ist (Freistellen, PNG mit Alpha), auch beim Senden. Die Vorschau im Slot zeigt weiter das dunkle Panel-Grau.
- **Alternativen:** Weiß (vorher), Schalter im Slot, Grün (Chroma-Key-Farbe; riskant, weil das Modell sie ins Bild übernehmen könnte).

## 11. Icon-Leiste in den Slots
- **Gewählt:** Eine schmale Leiste (22 Punkt breit) am rechten Rand INNEN im Slot, 16-Punkt-Symbole untereinander, gezeichnet wie `icon_image` (Pixelbild in `gui_common.SLOT_ART` bzw. Zeichenbefehle, keine Bilddateien). Jedes Symbol hat einen Tooltip „Wort: Erklärung“ mit dem alten Wort.
- **Gefüllter Slot (von oben nach unten):** Remove (Kreuz), Pen (Stift), Cut out / Undo cut (Schere), Describe (Textzeilen), Copy text (zwei Blätter, nur wenn es eine Beschreibung gibt). Cut out und Describe sind grau, solange ihr Auftrag läuft.
- **Nächster freier Slot:** Paste (Klemmbrett) und Add file (Blatt mit Plus). Die Textknöpfe „Paste“ und „Add file“ in der Kopfzeile sind weg.
- **Platz:** Slotbreite bleibt 108 Punkt (+6 Abstand). Die Leiste liegt im Slot, das Bild wird um 22 Punkt kleiner (86 Punkt). 5 Symbole à 20 Punkt = 100 Punkt, passt in 108 Höhe. Slots je Modell: Qwen 2, Fibo 2, Flux 2 3, Flux 3 3 (`max_refs`). Drei Slots brauchen 3 × 114 = 342 Punkt, das Fenster hat 380 − 24 = 356 nutzbar; also passt es bei 100 %. Bei 150 % Skalierung rechnet alles mit `_px` mit und bleibt im gleichen Verhältnis.
- **Alternative:** Leiste unter dem Bild (nimmt Höhe statt Breite, aber du wolltest rechts) oder Symbole nur beim Daraufzeigen (schwerer zu entdecken).

## 10. Kleinkram
- Commit-Titel beginnen mit `L2:` (statt "Window round N"), weil es keine Fenster-Runde ist.
- `tests/test_removebg.py` heißt jetzt `tests/test_slot_tools.py` (Freistellen und Beschreiben zusammen).
- Der Tk-Stub in `tests/test_gui_presets.py` kennt jetzt Frame, Label und Canvas.
- `tests/live_dnd.py` prüft tkinterdnd2 in einem Temp-Ordner, nicht in deinem Python.
- Git kann hier keine Lock-Dateien löschen: ich benenne sie in `.git/stale-*` um.

## 13. Beschreibung und Prompt (Runde 2)
- **Gewählt:** Der Beschreibungstext ist ein kurzer Satz (Prompt: „Describe the main subject of this picture in one short sentence: what it is, its colour and most striking feature. No preamble.“, höchstens 60 Zeichen-Token; live geprüft: „A black cat with striking yellow eyes sits in green grass, ...“, 5 s). Er steht unter dem Bild im Slot und wird beim Senden automatisch ans Ende des Prompts gehängt (`RefSlots.prompt_with_descriptions`), eine Zeile je Bild. Das Textfeld im Fenster bleibt unverändert.
- **Weg:** Der Knopf „Descriptions to prompt“ ist weg. „Copy text“ ist ein Symbol in der Leiste des Slots.
- **Alternative:** Die Zeilen sofort ins Textfeld schreiben (du siehst sie, aber sie stehen doppelt, wenn du neu beschreibst).
- **Beispiele je Modell:** `docs/prompt-aufbau.md`, erzeugt von `tests/test_prompt_aufbau.py --write`.
- **tkinterdnd2:** fest in `setup-windows.bat` (pip) und `pyproject.toml` (Extra `dnd`). Fehlt es, steht unter den Slots ein Hinweis, alles andere geht.

## 14. Prüfung: Eingänge und Nummerierung (Antwort auf ANTWORTEN.md, Runde 2)
Es stimmt alles wie besprochen: Bild in PhotoCraft = Bild 1, Slot 1 = Bild 2, Slot 2 = Bild 3. Eine Auswahl wird ignoriert (Modus läuft als Edit).

| Modell | offene Bild-Eingänge | Knoten je Slot | Tag im Prompt (Bild / Slot 1 / Slot 2 / Slot 3) | leerer Slot |
|---|---|---|---|---|
| Qwen 2.1 | 2 | LoadImage 13, 14 → `images.image_2`, `image_3` des Encoders | `<image1>` / `<image2>` / `<image3>` | Knoten und Verbindung werden entfernt |
| Fibo 2 | 2 | LoadImage 90, 91 → `images.image_2`, `image_3` | `<image_1>` / `<image_2>` / `<image_3>` | wie oben |
| Flux 2 Klein | 3 | je Slot LoadImage 301–303, VAEEncode 311–313, 2× ReferenceLatent (positiv, negativ) in der Kette | `image 1` / `image 2` / `image 3` / `image 4` | die ganze Kette des Slots wird entfernt, die Kette bleibt geschlossen |
| Flux 3 Klein | 3 | LoadImage 301–303 → `images.image1` … `image3` von ReferenceMultiLatent (Bild = `image0`) | `<ref_image_0>` / `_1` / `_2` / `_3` | Knoten und Eingang werden entfernt |

Nummerierung und Reihenfolge prüft `tests/test_refslots.py` am echten Graphen (Bild zuerst, Referenzen dahinter, Ketten geschlossen, ohne Zyklus).

**Ungetestet, bitte so lesen:** Das Tag-Muster `<ref_image_{i}>` für das lokale Flux 3 Klein ist meine Annahme. Die Doku nennt für den Cloud-Knoten „FLUX 3 Image“ `image 1`, `image 2`. Qwen und Fibo sind live bestätigt (frühere Runde), Flux 2 ebenso strukturell; ein echter Mehrbild-Lauf je Modell steht aus.

## Offen (nichts gebaut)
- **Flux 3 Layout-Prompt / BBox:** „FLUX 3 Image Layout Prompt“ (Kernknoten, `<obj_N>`) und die Zeichenfläche f3k-bbox-nodes gehören laut Doku zum Cloud-Knoten. Ob das lokale Flux 3 Klein sie versteht und ob man damit Referenzbilder platzieren kann, ist nicht belegt. Du testest von Hand; später evtl. PhotoCraft-Auswahl als Box.
- **Idealer Prompt für Multi Image Edit:** wird von Hand getestet; keine automatische Verfeinerung. `docs/prompt-aufbau.md` beschreibt nur den heutigen Stand.
