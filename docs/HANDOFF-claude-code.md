# Handoff: PhotoCraft x ComfyUI Plugin, Umstieg auf Claude Code (Stand 2026-10-26, 20:00)

Zweck: Alles, was der Chat weiß, damit eine neue Claude-Code-Sitzung direkt auf dem Rechner des Nutzers weiterarbeiten kann. Ersetzt `plugin-handoff-2026-10-25-abend.md` und `fibo-vgl-plugin-handoff.md` (dort stehen noch Bionic/VGL und der alte Stand). Lies zusätzlich `CLAUDE.md` und `PLAN.md` im Repo.

## 1. Rolle und Regeln des Nutzers (immer)
- Rolle: App-Programmierer, UI-Designer und ComfyUI-Experte. Der Nutzer schreibt Deutsch; erklärt wird in einfachem Deutsch, ohne Git-Jargon (er kennt sich mit Git kaum aus und will Git/Lane-Wartung nicht selbst machen).
- Schreibt er **Englisch**: zuerst seine Nachricht in korrektem Englisch zurückgeben („Corrected version of your message:“ + Zitat), dann antworten. Deutsch braucht das nicht; ein einzelner englischer Satz im deutschen Text wird kurz korrigiert.
- **An Entscheidungspunkten die Optionen nennen** (mit Empfehlung als erste Option), nicht still wählen. Er will immer an die Wahlmöglichkeiten erinnert werden.
- Nebenwirkungen (Downloads, Neustarts, Löschungen, GPU-Läufe, Installationen) nur mit Erlaubnis. ComfyUI und Plugin startet er selbst neu.
- Git: pro Aufgabe ein beschreibender Commit, **nie pushen**. Trailer: `Co-Authored-By: Claude <Modellname> <noreply@anthropic.com>` (je nach Sitzung der dort vorgegebene Trailer).
- Keine README-Politur. `README.pl.md` ist Upstream und bleibt. `photocraft-ai 0.15.1.bat` ist sein Starter: nie löschen (`photocraft-ai.bat` zeigt noch auf 0.14.0, offene Frage, ob angleichen).
- `undo.png` im Repo-Wurzelordner bleibt absichtlich **ungetrackt**, bis die Fenster-Politur-Lane sie nach `pccomfy/assets/` verschiebt.
- Checkpoint-Graph und Fooocus-Code bleiben vorerst („jetzt mal nicht“). Keine automatische Prompt-Ergänzung bei „remove …“ (nur Tipp unter dem Prompt).
- Sein Bildton: Fenster 380 px fest breit, Titelleiste bleibt `#404040`, alles andere Hintergrund `#282828`.

## 2. Repo und Git-Stand
- Pfad `C:\programs\photocraft-comfyui-bridge` (Windows), Fork von Peszemeszek/photocraft-comfyui-bridge. Nur lokal, nichts gepusht.
- Branches: `main` (Upstream 9bd94be), `windows-fibo` (abgenommener Stand 6aff33a), `refactor/split-gui` (Phase 0), **`next` = Integrationsstand, aktuell abe50e7** (den testet der Nutzer). Tag `backup-2026-10-26` (6df02df) und ein ZIP des Nutzers.
- Lane-Ordner `lanes/L1` (Branch `feat/l1-detection`, ec9863e) und `lanes/L2` (`feat/l2-multi-image`, daa3c60) sind eigenständige Klone, vom Haupt-Repo über `.git/info/exclude` ignoriert; beide sind vollständig in `next` gemergt. Darin liegen ungetrackt `FRAGEN.md` und `ANTWORTEN.md` (Kopien liegen jetzt in `docs/archiv-lanes/`).
- Merge-Ablauf bisher: `git fetch lanes/Lx <branch>:refs/lanes/lx`, dann `git merge --no-ff` in `next`, vorher/nachher `python tests/run_all.py`.
- Auf dem Cloud-Rechner (VM) gab es kein tkinter; mit Claude Code lokal auf Windows gibt es das echte Fenster. Die Tests laufen gegen gestubbtes Tk (39 Dateien, alle grün, ca. 15 s): `python tests/run_all.py [Namensfilter]`.
- Diagnose: `data/exchange/last-graph.json` (zuletzt gesendeter Graph) und `data/exchange/runs.jsonl` (eine Zeile je Lauf: Funktion, Workflow, Seed, Größe, Prompt).
- Sein Python: `data/python.txt` (zeigt auf `.venv\Scripts\python.exe`). `setup-windows.bat` installiert pillow, numpy, websocket-client, tkinterdnd2.

## 3. Umgebung
- ComfyUI: `C:\programs\ComfyUI-Easy-Install Cuda13\ComfyUI` (0.42.0), Modelle in `C:\AI_Models` und `D:\AI_Models`. LoRA-Ordner liest ComfyUI nur beim Start. Hardware: RTX 4070 Ti Super (16 GB), 64 GB RAM. Release 1 gilt nur für 16 GB.
- Weitere Hintergründe in den Projektdokumenten: `shipping-photocraft-comfyui-plugin.md`, `shipping-addendum-1-ausboss-folders-downloads.md` (Modell-Downloadlinks, Ordner-Erkennung, AusBoss-Ersatz), `plugin-erfahrungen*.md` (Testergebnisse des Nutzers). AusBoss-Nodes bleiben als Abhängigkeit.

## 4. Was gebaut und in `next` ist
**Phase 0:** `gui.py` in Mixins geteilt (`App(SettingsMixin, RefSlotsMixin, ThemeMixin, PromptMixin, LoraMixin, ModeMixin, StateMixin, RunMixin)`; Dateien `gui_common.py` (Konstanten, Re-Export), `gui_theme/prompt/lora/modes/state/run.py`); `Model` mit `max_refs`, `tag_style`, `requires`; `clipboard.py` (Windows-Zwischenablage per ctypes: PNG + CF_DIB schreiben, PNG/DIB/ImageGrab lesen); Krea 2 und Flux 3 ohne Expand; „(1 doc.)“ weg; „Done“ allein grün `#39A95D`, Zeile „Done · seed N · created N layers · Zeit“; `tests/run_all.py`.

**L1 (Erkennung/Settings):** `manifest.py` (Python-Daten, drei Ebenen: Pflicht je Tab, extra je Modus, optional), `inventory.py`, `ui_settings.py` (Zahnrad unten rechts in der Fußzeile, Einstellungsfenster hängt wie das Plugin-Fenster an PhotoCraft, `preset_blocked()`), Preflight vor Generate, Einstellungen in `data/settings.json`. Tab-Zustände: inaktiv `#282828`, aktiv wie vorher, nicht verfügbar rote Schrift (`NA_RED`). Startzustand: allererster Start ohne Modell und ohne Parameter; danach bleibt das zuletzt gewählte Modell; ohne verlinkte Modelle nur „Link your model in the settings“ plus Zahnrad; fehlt das letzte Modell, ist kein Tab gewählt mit Meldung. `PANEL` zentral `#282828`. Doku: `docs/entscheidungen-L1.md`.

**L2 (Multi Image Edit):** Modus `multi_edit` ersetzt „Insert reference image“ (Modus „Reference“ entfällt) bei Qwen, Fibo, Flux 2, Flux 3; Slots nur in diesem Modus, Ausführung über den Edit-Workflow des Modells (`run_as="edit"`), Auswahl wird ignoriert. Nummerierung: PhotoCraft-Bild = Workflow-Bild 1, Slot 1 = Bild 2 usw.; leere Slots werden aus dem Graphen entfernt (`drop_ref_slot`, `_meta.pc_slot`/`pc_pass`). Tag-Schreibweise je Modell: Qwen `<image{n}>`, Fibo `<image_{n}>`, Flux 2 `image {n}`, Flux 3 `<ref_image_{i}>` (zählt ab 0, `ref_image_0` = Hauptbild); beim Modellwechsel werden Tags im Prompt automatisch umgeschrieben. Slot-Widget (`refslots.py`): Icons rechts am Rand (+70 %, Pen entfernt), Ctrl+V, Drag and Drop (tkinterdnd2, vom Nutzer erfolgreich getestet), Freistellen (BiRefNet, Workflow `birefnet-remove-bg.json`, grauer Hintergrund zum Testen, Nutzer: „funktioniert super“), Beschreiben (Qwen 3.5 9B, `describe-image.json`, kurzer Satz unter dem Bild und hinten am Prompt, Kopier-Icon je Slot), Image-Tag zentriert, „Max. images: x“ immer sichtbar, Tipp unter dem Prompt („You can start with a white image and use the reference images below to place them on the canvas.“). Slotzahl: Qwen 8 (reihenweise ab dem 4.), Fibo 2, Flux 2 und Flux 3 je 3 (`max_refs` in `models.py`). `prepare_image`: flach auf Grau, höchstens 1024 px. Docs: `docs/entscheidungen-L2.md`, `docs/prompt-aufbau.md` (echter Gesamtprompt je Modell), `docs/prompting-multi-image.md` (belegt / Handtests / Vermutungen getrennt).

**Flux 3 Klein BBox (nur recherchiert, nichts gebaut):** `docs/flux3-bbox-workflow-notes.md`. Nutzer-Workflow „image_flux3_klein_distilled_image_edit_bbox test“ funktioniert bei ihm. Kette: `CreateBoundingBoxes` (Kernknoten; optionaler Eingang `bboxes`) → `Flux3LayoutPrompt` (Kernknoten, reiner Text) → Prompt mit `<ref_image_0>` (Hauptbild), `<ref_image_1>` (erstes Referenzbild), `<obj_N>`; Box `[ymin,xmin,ymax,xmax]` auf Skala 0 bis 1000; `ReferenceMultiLatent`. KJNodes `Flux3PromptBuilderKJ` beschreibt Referenzbild-Boxen ausdrücklich (ungetestet). Das Paket f3k-bbox-nodes ist nur eine Zeichenfläche für die alte Oberfläche.

## 5. Entscheidungen des Nutzers (komplett)
- Release 1 nur 16 GB getestet, 8-GB-Empfehlungen nur als Doku. Fast Mode gestrichen. Krea 2 Expand und Flux 3 Expand deaktiviert.
- Veröffentlichung: neues Repo ohne Upstream-Verlauf, Lizenz-Credits bleiben Pflicht; Zeitpunkt erst kurz davor; bis dahin Branch `windows-fibo`.
- Reihenfolge: zuerst Modell-Erkennung, **Easy Mode zum Schluss** (braucht L1, L2 und Hide/Show aus L3). Easy-Mode-Ranking: Fill Qwen, Fibo (Flux später); Expand MOSS, Flux 2, Fibo, Qwen. Datensatz in `easymode.py`; „Favorit“ aus dem Rechtsklick überschreibt ihn je Funktion.
- Rechtsklick auf Modell-Tab: als Favorit setzen, Tab ausblenden, Workflow-JSON mit allen Settings speichern (ob sein ComfyUI-Frontend API-JSON lädt, ist ungeprüft; sonst Umwandlung ins Editor-Format).
- Minimize = Einklappen zur Titelleiste, Button hide/show. Undo/Redo-Buttons mit seiner `undo.png` (Redo gespiegelt), Funktion bleibt.
- Krea-2-Styles: bis zu 50, per Bildauswahl (Repo klonen, Bilder wählt er, Lizenz vorher klären), Prompt-Templates per Klick. Tutorial-PSDs vorerst nur mit Testbild. Tooltips bei jedem Start.
- OpenFill-Recherche: PhotoCraft-Befehle prüfen (`select.modify.feather`, History-Snapshots, `image.crop` u. a.); Seam-Korrektur nur als A/B-Test mit deutlich sichtbarem Unterschied; Live-Vorschau (TAESD vorhanden) unten; Verlauf der letzten 20 Läufe mit erneutem Laden; kein Varianten-Picker; Cancel/Undo und Shift+Enter (neue Zeile) / Strg+Enter (Run) bleiben; Modell-Manager von OpenFill nach Repo-Download vergleichen.
- Qwen 2.1: sein Workflow hat 9 Image-Inputs, im Plugin mehr als 2 Slots (jetzt 8).
- „Insert reference image“ wird durch „Multi Image Edit“ ersetzt (nur Edit-fähige Modelle).

## 6. Offene Entscheidungen (Nutzer hat noch nicht geantwortet)
1. **Qwen-Slotzahl für 16 GB** (L2-Frage 8): A (empfohlen) 8 lassen und er testet 2/4/8; B vorerst 4; C Bilder automatisch kleiner machen (z. B. 8 Bilder höchstens 512 px). Konstante `max_refs` in `models.py`.
2. **Flux-3-Boxen** (L2-Frage 9): A (empfohlen, erst testen) Textlauf von `Flux3LayoutPrompt` mit einer Box, danach Plugin baut die Tabelle selbst und hängt sie an den Prompt; B Plugin fügt `CreateBoundingBoxes` + `Flux3LayoutPrompt` in den Flux-3-Workflow ein (Box aus der PhotoCraft-Auswahl); C nichts bauen, von Hand testen. Bisher gewählt: „PhotoCraft-Auswahl = Box“, je Slot ein Icon „Auswahl als Ort verwenden“ plus Beschreibung. Zu klären: ob er die zwei Textläufe (praktisch ohne GPU) erlaubt; ein echter Bildlauf braucht seine GPU-Erlaubnis. Unregelmäßige Auswahl würde auf ihr Umschlagrechteck reduziert.
3. **Alter Knopf „Insert reference image“** im Fenster: war grau, Entfernung gehört zur Fenster-Politur (L3). Prüfen, ob er in `next` noch sichtbar ist.
4. Weitere offene Punkte: `photocraft-ai.bat` auf 0.15.1 angleichen? Checkpoint-Graph/Fooocus später entfernen? Scribble/Sketch, Remove-Prompt-Formulierungen, Encoder-Tausch, Steps-Prüfung (Recherche/Test ohne Code, `docs/tests/`).

## 7. Der Nutzer muss noch live testen (`next`)
Bereits bestätigt: Drag and Drop, Cutout, Referenzieren („the woman in <image2> is sitting on a beach“ auf weißer Fläche). Noch offen: Zahnrad unten rechts und Fußzeilenbreite bei 380 px; Tab-Farben/-Zustände; Startzustände (leer, letztes Modell); Einstellungsfenster-Verhalten beim Schließen von PhotoCraft; Slot-Änderungen der Runde 3 (Icon-Größe, zentrierter Tag, „Max. images: x“, Tag-Umschreiben beim Modellwechsel, Tipp-Text); Qwen mit 2/4/8 Bildern; Beschreibungstext im Prompt; **Settings-Fenster mit leerem Modellordner** (er simuliert den später); Layout bei 150 % Skalierung; Krea 2 Turbo Expand; Flux 2 Scheduler-Auswahl; Flux 2 T2I mit/ohne Enhancer.

## 8. Nächste Schritte (Vorschlag, Reihenfolge)
1. Offene Entscheidungen 6.1 und 6.2 klären, danach die Live-Tests aus Abschnitt 7.
2. **L3 Fenster-Politur** (er startet sie nach dem Test von `next` in einem neuen Chat): Hide/Show-Button (Einklappen zur Titelleiste), Undo/Redo-Icons mit `undo.png` (nach `pccomfy/assets/`, `pyproject.toml` package-data), Rechtsklick-Menü (Favorit, ausblenden, Workflow-JSON speichern), PhotoCraft-Look der Slider/Haken, „Copy canvas to clipboard“, alten Knopf „Insert reference image“ entfernen.
3. **L4 Inhalte:** Krea-Style-Chooser, Tipps/Tooltips, Tutorial-PSDs, `docs/`.
4. Flux-3-Boxen (je nach Entscheidung), danach **Easy Mode** (`easymode.py`) zuletzt.
5. Vor der Veröffentlichung: neues Repo (ohne Upstream-Verlauf, Credits), README-Windows prüfen, Release-Prüfung auf 16 GB.

## 9. Hinweise zum Umstieg auf Claude Code
- Lokal auf Windows entfällt die VM-Beschränkung: echtes tkinter, das Fenster kann direkt gestartet und angesehen werden; Git-Sperrdateien (`.git/*.lock`, `tmp_obj_*`) machen dort keine Probleme.
- Die Lane-Klone (`lanes/L1`, `lanes/L2`) sind nur noch Altlast; für neue Arbeit reichen Branches aus `next` (oder `git worktree`, falls zwei Aufgaben parallel laufen sollen). Option A: weiter mit eigenen Lane-Chats und dem FRAGEN/ANTWORTEN-Ablauf; Option B: eine einzige Claude-Code-Sitzung, die Branch für Branch arbeitet und ihn nach grünen Tests in `next` mergt (einfacher, nichts mehr kopieren). **Entschieden 2026-10-26: Option B.**
- Lane-Protokoll (falls beibehalten): rein technische Entscheidungen trifft die Lane selbst und protokolliert sie samt Alternativen in `docs/entscheidungen-Lx.md`; sichtbare Fragen in `FRAGEN.md` (Nummer, Optionen, Empfehlung zuerst), Antworten in `ANTWORTEN.md`.
- Dieses Dokument liegt im Repo unter `docs/HANDOFF-claude-code.md` und im Claude-Projekt als `claude/handoff-claude-code-2026-10-26.md`. Das Projekt-Gedächtnis (`plugin-roadmap`) enthält dieselben Entscheidungen.
