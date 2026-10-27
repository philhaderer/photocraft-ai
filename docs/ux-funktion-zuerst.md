# UX-Frage D.15: Funktion zuerst, Modell darunter?

Stand 2026-10-27. Recherche, nichts gebaut. Entscheidung des Users offen.

## Heute

Oben 6 Modell-Tabs (3 Zeilen à 2), darunter 8 Funktionen (4 Zeilen à 2). Was das gewählte Modell nicht kann, ist grau.

Welche Funktion welches Modell kann (`models.py`):

| Funktion | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS | Anzahl |
|---|---|---|---|---|---|---|---|
| Text to image | x | x | x | x | x | x | 6 |
| Expand image | x | x | x | x | x | x | 6 |
| Fill Selection | – | – | x | x | – | – | 2 |
| Remove Selection | x | x | x | x | – | – | 4 |
| Edit whole image | x | x | x | x | – | – | 4 |
| Multi Image Edit | x | x | x | x | – | – | 4 |
| Upscale | x | x | – | – | – | – | 2 |
| Refine | – | x | – | x | – | – | 2 |

Befund: Krea 2 und MOSS können nur 2 von 8 Funktionen. Wer heute MOSS wählt, sieht 6 graue Funktionen. Umgekehrt hat jede Funktion mindestens 2 Modelle: Eine Funktion zuerst führt nie in eine Sackgasse.

## Optionen

**A. Funktion oben, Modell als Dropdown darunter (empfohlen)**
- Die 8 Funktionen bleiben als Radios oben (2 Spalten). Darunter eine Zeile „Model: [Dropdown]“, die nur die Modelle zeigt, die die Funktion können. Das empfohlene Modell steht zuerst („Qwen 2.1 Edit (recommended)“).
- Platz: 1 Zeile statt 3 Zeilen Tabs. Bei 380 px Breite der größte Gewinn.
- Graue Einträge gibt es nur noch für Modelle, deren Dateien fehlen (rot, „set in settings“), nicht mehr für „kann diese Funktion nicht“.

**B. Funktion oben, Modell-Tabs darunter**
- Wie A, aber die passenden Modelle als Tabs (bei Fill 2 Tabs, bei Text to image 6 Tabs in 3 Zeilen).
- Die Fensterhöhe springt mit jeder Funktion; mehr Platz als A.

**C. Bleibt wie heute (Modell zuerst)**
- Passt für Nutzer, die ihr Modell kennen. Kein Umbau.

## Folgen eines Umbaus (A oder B)

- **Gesperrte Kombinationen:** Es gibt keine grauen Funktionen mehr. Wechselt man die Funktion und das gewählte Modell kann sie nicht, springt das Modell um. Dafür braucht es „letztes Modell je Funktion“ als neuen Eintrag im gespeicherten Zustand, sonst springt es beim Zurückwechseln nicht mehr zurück.
- **Start- und Leerzustände** (`start_state`, ui_settings.py): Aus „Choose a model“ wird „Choose a function“. „Link your model in the settings“ (nichts installiert) bleibt.
- **Easy Mode passt sehr gut dazu:** Das Ranking je Funktion wird zum Startwert des Dropdowns. Easy Mode wäre dann fast nur noch „Dropdown ausblenden, das empfohlene Modell nehmen“. Ein Umbau vor dem Easy Mode spart dort Arbeit. Dafür fehlt noch das Ranking für Text to image, Remove, Edit, Multi Image Edit, Upscale und Refine (heute gibt es nur Fill und Expand).
- **Rechtsklick-Menü (L3):** Aus „Favorit für den Tab“ wird „als Standard für diese Funktion“ im Dropdown; „Tab ausblenden“ wird „Modell ausblenden“ (in den Settings).
- **Tooltips:** Heute erklärt der Tooltip der Funktion, was das gewählte Modell darin tut (`mode_tips`). Ein ttk-Dropdown kann keine Tooltips je Eintrag zeigen: Die Erklärung des gewählten Modells käme als Tooltip auf das Dropdown oder als kurze Zeile darunter.
- **Gespeicherter Zustand, Presets:** Bleiben gleich (Modell + Funktion werden schon gespeichert); neu nur „letztes Modell je Funktion“.
- **Starteinstellungen je Modell** (Turbo, LoRA, Steps): bleiben je Modell-Funktion-Paar in `models.py`, nichts ändert sich an den Daten.
- **Code:** `models.py` und die Workflows bleiben. Umgebaut würden `gui.py` (Kopf), `gui_modes.py` (`_on_model`, `_update_mode_radios`), die grauen Tabs in `ui_settings.py` und ihre Tests (`test_model_tabs.py`, `test_settings_ui.py`, Teile von `test_round5.py`). Mittelgroß, etwa so groß wie Liste A.
- **Achtung:** Die Tab-Zeile gehört zum Fensterkopf, den der User „perfekt“ nennt. Ein Umbau ändert ihn bewusst.

## Empfehlung

Option A, und zwar vor dem Easy Mode (er baut darauf auf). Vorher braucht es vom User das Ranking für die sechs Funktionen ohne Ranking. Bis dahin bleibt es wie heute.
