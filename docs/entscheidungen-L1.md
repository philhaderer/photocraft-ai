# Entscheidungen Lane L1 (Modell-Erkennung / Settings)

Rein technische Entscheidungen, die ich selbst getroffen habe. Jede hat die gewählte Option (zuerst) und die Alternativen.
Zum Umdrehen: Nummer nennen. Stand 2026-10-26, Branch `feat/l1-detection`.

## 1. Manifest als Python-Daten in `manifest.py`
- Gewählt: Python-Datei (testbar, kein Einlesen nötig). Vom User freigegeben.
- Alternativen: `data/manifest.json` (leichter austauschbar, aber `data/` ist git-ignoriert); Block in `models.py` (Datei gehört L2).

## 2. Drei Stufen: Pflicht je Tab, Zusatz je Modus, optional
- Gewählt: fehlt eine Pflichtdatei, ist der Tab grau; fehlt eine Zusatzdatei, nur der Modus; optionale Dateien (Schnell-LoRAs, Prompt-Schreiber) nur ein Hinweis. Vom User freigegeben.
- Alternativen: Tab grau bei jeder fehlenden Datei; nur Hinweise, nichts sperren.

## 3. Zuordnung Modus -> Dateien liegt im Manifest, `requires` in `models.py` ist nur die Pflichtmenge des Tabs
- Gewählt: wie vom User freigegeben. Ein Test hält beide gleich.
- Alternative: neues Feld in `Mode` (Änderung an `models.py`, gehört L2).

## 4. Dateinamen aus den echten Workflows, nicht aus dem Shipping-Doc
- Gewählt: das, was die JSON-Dateien laden (ein Test vergleicht beides). Das Doc weicht z. B. bei Qwen (andere Textencoder je Modus) und Fibo ab.
- Alternative: Doc als Wahrheit nehmen und Workflows anpassen (würde Dinge ändern, die du als „perfekt" kennst).

## 5. Namenssuche `resolve()`: eigene Verknüpfung, exakt, Groß/Klein und `\`/`/`, Alias, eindeutiger Dateiname in anderem Unterordner
- Gewählt: tolerant, aber bei zwei Treffern kein Raten.
- Alternativen: streng (nur exakt); immer den ersten Treffer nehmen.

## 6. Namen werden beim Senden ersetzt: `ComfyUI.name_fixer` in `comfy.py` (`queue`)
- Gewählt: ein Haken in `comfy.py` (meine Datei), `bridge.py` bleibt unberührt.
- Alternative: Aufruf in `bridge.py` (gehört L2, Konfliktgefahr).

## 7. Eigene Verknüpfungen, yaml-Pfad, Favoriten, ausgeblendete Tabs in `data/settings.json`
- Gewählt: eigene Datei neben `state.json`, kleine Funktionen in `config.py`.
- Alternativen: alles in `state.json` (vermischt mit Fensterzustand); in `config.toml` (nur lesbar, kein Schreiben vorgesehen).

## 8. `extra_model_paths.yaml` mit eigenem kleinen Leser, nur lesen
- Gewählt: kein PyYAML (keine neue Abhängigkeit), versteht das flache Format von ComfyUI.
- Alternativen: PyYAML (genauer, neue Abhängigkeit); Datei weglassen.

## 9. Ablauf der Erkennung
- Gewählt: beim Start, per Refresh (auch der Knopf unten im Fenster) und vor Generate (nur wenn der Zwischenspeicher „fehlt" sagt, dann einmal frisch lesen). ComfyUI nicht erreichbar = nichts wird gesperrt.
- Alternativen: nur Start und Refresh; regelmäßig im Hintergrund (mehr Last).
- Gelesen wird `/object_info` einmal ganz (auch Node-Klassen).

## 10. Einbau ins Fenster
- Gewählt: `SettingsMixin` steht in `App` vorn und ruft `super()` (refresh, `_apply_refresh`, `_update_mode_radios`, `_on_model`, generate); Ergebnis kommt als „refresh"-Ereignis; Tab-Tooltips über `tt_tabs`.
- Alternative: Änderungen in `gui_state.py`, `gui_modes.py`, `gui_run.py` (gehören nicht L1, mehr Konflikte).
- Folge: `tests/test_phase0.py` erwartet jetzt `SettingsMixin` vor den sechs Mixins und ein befülltes `requires`.
- Richtigstellung zu FRAGEN 3: Ein Preset ruft `_on_model` gar nicht auf (`gui_state._apply_settings` setzt nur den Workflow, `_sync_model` wählt daraus den Tab). Ein Preset mit fehlendem Modell wird also heute ganz geladen und der Tab erscheint als „nicht verfügbar"; Generate wird vom Preflight gestoppt. Das Öffnen der Einstellungen gibt es nur beim Klick auf den Tab.

## 11. Download-Links
- Gewählt: nur Links aus den Projekt-Notizen; unbekannte Quellen bleiben leer, unsichere sind als „wahrscheinlich" markiert.
- Alternative: Links raten (nicht gemacht).

## 12. Git
- Zwei Commits (Aufgabe 6; Aufgaben 7 und 8 zusammen, weil sie in `ui_settings.py` verbunden sind). Reste von Git (.lock, tmp_obj) liegen als `.git/stale-*`, weil Löschen nicht erlaubt ist.

## 13. Einstellungs-Fenster hängt an PhotoCraft (Antwort 1 A + Ergänzung)
- Gewählt: das Fenster gehört dem Hauptfenster der Brücke (Tk `transient` plus `winlink` set_owner), das wiederum PhotoCraft gehört. Es liegt über beiden, nie über anderen Programmen, und wird mit ihnen versteckt, minimiert und geschlossen. „Immer im Vordergrund" (topmost) ist weg, das war die Ursache, dass es nach dem Schließen von PhotoCraft sichtbar blieb.
- Alternative: das Fenster direkt an PhotoCraft hängen (wäre bei PhotoCraft-Menüs im Weg, weil nur das Hauptfenster dafür versteckt wird).

## 14. Preset mit fehlendem Modell: Änderung für den Haupt-Chat (Antwort 3 A, nicht von mir gemacht)
Gewünscht: das Preset lädt nur, was geht; das Modell mit fehlenden Dateien wird nicht gewählt, und die Meldung sagt, was fehlt.
- Datei: `pccomfy/gui_state.py`, Methode `_apply_settings` (ab Zeile 91).
- Hilfsfunktion von mir (fertig, getestet): `self.preset_blocked(s)` in `ui_settings.py`. Sie gibt `""` zurück, wenn Modell und Modus laufen können, sonst einen Satz wie „Krea 2 Turbo is missing files: qwen_image_vae.safetensors (see settings)".
- Änderung: direkt nach `notes: list[str] = []` (Zeile 94) einfügen:
  ```python
  blocked = self.preset_blocked(s)
  if blocked:
      notes.append(blocked)
      s = {k: v for k, v in s.items() if k not in ("mode", "workflow", "model")}
  ```
  Damit werden Zeile 102 (`put(self.v_mode, "mode", str)`) und Zeilen 103 bis 109 (Workflow) für dieses Preset übersprungen. Der Rest des Presets (Text usw.) wird wie bisher gesetzt; `_sync_model` (Zeile 174) lässt dann den bisherigen Tab stehen. Die Meldung erscheint durch `load_preset` (Zeile 229) als „Not applied: ...".
- Offen für den Haupt-Chat: ob Regler, die zu diesem Modell gehören (Auflösung, Stärke), mit ausgenommen werden sollen. Ich würde sie mitnehmen (sie sind harmlos), damit nichts halb zum falschen Modell passt, bräuchte es eine Liste der Schlüssel.
