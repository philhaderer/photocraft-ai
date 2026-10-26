# Handoff: PhotoCraft x ComfyUI Plugin (Stand 2026-10-26, 22:15)

Zweck: Alles, was die nächste Claude-Code-Sitzung wissen muss, um direkt weiterzuarbeiten. Lies zusätzlich `CLAUDE.md` (Arbeitsweise, Regeln) und `PLAN.md` (Plan, Lanes). Die Sitzung vom 26.10. abends (Claude Code, Opus 5.5) hat diesen Stand geschrieben; die Aufgabenliste für den nächsten Chat steht in **Abschnitt 6**.

## 1. Rolle und Regeln des Nutzers (immer)
- Rolle: App-Programmierer, UI-Designer und ComfyUI-Experte. Der Nutzer schreibt Deutsch; erklärt wird in einfachem Deutsch, ohne Git-Jargon.
- Schreibt er **Englisch**: zuerst seine Nachricht in korrektem Englisch zurückgeben („Corrected version of your message:“ + Zitat), dann antworten.
- **An Entscheidungspunkten die Optionen nennen** (Empfehlung zuerst), nie still wählen. Bei Wortlaut/Tooltips/Design im Zweifel fragen.
- Nebenwirkungen (Downloads, Neustarts, Löschungen, GPU-Läufe, Installationen) nur mit Erlaubnis. ComfyUI und Plugin startet er selbst neu.
- **Git nach Standard und nachvollziehbar** (Details `CLAUDE.md`): je Änderung ein Branch aus `next` (`feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`), nie direkt auf `next`; Tests grün, dann `git merge --no-ff` in `next`; nie pushen, nie Verlauf umschreiben. Conventional Commits (`typ: Zusammenfassung`, Body mit Was und Warum), Trailer mit dem Modell der laufenden Sitzung. Nach jedem Git-Schritt auf Deutsch sagen, was passiert ist. **Vor jedem Löschen eines Branches fragen** (Entscheidung 26.10.).
- In PowerShell mehrzeilige Commit-Nachrichten mit `git commit -F <datei>` (Datei im Scratchpad); Here-Strings mit Anführungszeichen haben einmal die Argumente zerlegt.
- Keine README-Politur. `README.pl.md` ist Upstream und bleibt. `photocraft-ai 0.15.1.bat` ist sein Starter: nie löschen.
- Checkpoint-Graph und Fooocus-Code bleiben vorerst. Keine automatische Prompt-Ergänzung bei „remove …“ (nur Tipp unter dem Prompt).
- Sein Bildton: Fenster 380 px fest breit, Titelleiste `#404040`; Flächen `#282828` (`PANEL`), Fenstergrau `#535353` (`BG`), Akzent Orange `#f28c28`.
- „Perfekt“ (nicht ohne Nachfrage anfassen): Qwen 2.1 Edit/Fill/Expand/Remove; Flux 2 und Flux 3 Edit; Flux 3 Upscale; Flux 3 Text to image; MOSS Text to image und Expand; Fibo Edit whole image; Fensterkopf und Schärfe des Fensters.

## 2. Repo und Git-Stand
- Pfad `C:\programs\photocraft-comfyui-bridge`, Fork von Peszemeszek/photocraft-comfyui-bridge. Nur lokal, nichts gepusht.
- Branches: `main` (Upstream), `windows-fibo` (abgenommener Stand 6aff33a), `refactor/split-gui` (Phase 0, in `next`), **`next` = Integrationsstand, den der Nutzer testet**.
- Sonst keine Branches: alle Arbeits-Branches der Sitzung vom 26.10. sind gemergt und mit Erlaubnis des Nutzers gelöscht (die Commits stecken in `next`). Künftig: Löschen nur nach Rückfrage.
- Tags: `backup-2026-10-26` (6df02df, vor Phase 0), **`vor-claude-code`** (65e955f, letzter Stand vor dem Umstieg auf Claude Code).
- Lane-Klone `lanes/L1`, `lanes/L2` sind Altlast (per `.git/info/exclude` ignoriert, vollständig gemergt). Archiv der Lane-Fragen: `docs/archiv-lanes/`.
- Tests: `python tests/run_all.py` (39 Dateien, alle grün unter Windows, ca. 16 s). Python des Nutzers: Pfad in `data/python.txt`.
- Diagnose: `data/exchange/last-graph.json` (zuletzt gesendeter Graph), `data/exchange/runs.jsonl` (eine Zeile je Lauf). ComfyUI-Historie ist lokal über `http://127.0.0.1:8188/history` lesbar (so wurde der Seed-Befund unten gefunden).

## 3. Umgebung
- ComfyUI: `C:\programs\ComfyUI-Easy-Install Cuda13\ComfyUI` (0.42.0), Modelle in `C:\AI_Models` und `D:\AI_Models`. RTX 4070 Ti Super (16 GB), 64 GB RAM. Release 1 nur 16 GB.
- PhotoCraft 0.15.1 portable unter `C:\programs\photocraft-0.15.1-windows-x64-portable`.
- Hintergrund-Dokumente im Claude-Projekt: `shipping-photocraft-comfyui-plugin.md`, `shipping-addendum-1-ausboss-folders-downloads.md` (Modell-Downloadlinks, Ordner-Erkennung, AusBoss), `plugin-erfahrungen*.md`. Im Repo: `ideas.md` (OpenFill-Ideen T1 bis T4).
- Echtes Tk lässt sich lokal prüfen: ein Skript, das `tk.Tk.__init__` mit `withdraw()` umhüllt, `PCCOMFY_HOME` auf einen Temp-Ordner setzt und `gui.App(cfgmod.load())` baut, kann Höhen messen; mit `PIL.ImageGrab` lässt sich das sichtbare Fenster fotografieren (`gui.winlink.available = lambda: False` vorher, sonst hängt es sich an PhotoCraft).

## 4. Was gebaut und in `next` ist
**Phase 0, L1, L2** wie im Plan (Mixins, `clipboard.py`, Modell-Erkennung mit Zahnrad und Preflight, Multi Image Edit mit Slots, Tags je Modell, Freistellen, Beschreiben). Details: `docs/entscheidungen-L1.md`, `docs/entscheidungen-L2.md`, `docs/prompt-aufbau.md`, `docs/prompting-multi-image.md`.

**Sitzung 26.10. abends (Claude Code):**
- Doku: Conventional Commits und Branch-Ablauf in `CLAUDE.md`; Arbeitsweise „eine Sitzung, Branch für Branch“ (statt Lane-Chats).
- Tests laufen unter Windows (Workflows/Presets der Tests in Temp-Ordner umgeleitet, `owner_present` im Winlink-Test vorgetäuscht, Runner liest UTF-8).
- `undo.png` liegt in `pccomfy/assets/undo.png` (package-data); `ideas.md` getrackt.
- Slots: „Max. images: x“ steht in der Kopfzeile neben „Reference images (n/x)“.
- Beschreiben schreibt `<image2>: …` **sichtbar** ans Ende des Prompt-Felds; erneutes Beschreiben ersetzt die unveränderte Zeile; eine von Hand geänderte oder gelöschte Zeile bleibt, das Fenster sagt es. Gesendet wird das Feld, wie es dasteht (`RefSlots.put_description`).
- Neue Slot-Icons als Vektorformen: `pccomfy/icons.py` (24er-Raster, Strich 2, runde Enden, Lucide-Stil, ISC: **in den Release-Credits nennen**), 8-fach gezeichnet und auf die echte Pixelgröße verkleinert; unter der Maus orange. `ICON_PX = 24` in `refslots.py`. Vom Nutzer gelobt („super, sehr schön“).
- Starter `photocraft-ai neuer-nutzer.bat`: eigener Datenordner `data\neuer-nutzer` (`PCCOMFY_HOME`), Menü 1 bis 4 (erster/weiterer Start, mit/ohne Modelle; „ohne Modelle“ = `PCCOMFY_SIMULATE_NO_MODELS=1` in `inventory.fetch`). PhotoCraft vorher schließen. Noch nicht vom Nutzer benutzt.
- Expand für **Flux 3** und **Krea 2** wieder eingeschaltet (zum Testen).
- Dünner Scrollbalken: alles unter den Tabs liegt in einem Canvas (`f_scrollbox`, `cv_body`, `f_body`); `_fit_height` begrenzt das Fenster auf den Platz bis zum Bildschirmrand (`_max_height`), sonst erscheint `ThinScrollbar` (gui_common.py, 6 px, Griff `#808080`). Mausrad scrollt, Textfelder/Listen nicht. Generate liegt im gescrollten Teil.
- Masken-Analyse (nur Befund, nichts geändert): Bei Fill/Remove ohne Masken-Workflow (Qwen, Flux 2/3 Remove, Fibo) ist die Ebenenmaske an der Auswahlkante nur ca. 50 % deckend (`auto_feather` blurt ohne vorheriges Wachsen) → Geister-Umriss bei Remove. Option A (empfohlen, offen): erst um den Feather-Radius wachsen, dann blurren (OpenFill-Art), nur Flux 2/3 Remove und Fibo Fill/Remove; Qwen nur mit OK.

## 5. Entscheidungen des Nutzers (komplett)
- Release 1 nur 16 GB, 8-GB-Empfehlungen nur Doku. Fast Mode gestrichen.
- Krea 2 Expand und Flux 3 Expand: am 26.10. abends wieder an zum Testen. **Ergebnis:** Flux 3 Expand funktioniert (vermutlich wegen mehr Steps, im Fenster 15); Krea 2 Expand nur einseitig brauchbar (siehe 6.10). Endgültige Entscheidung steht aus.
- Qwen-Slotzahl: **8 bleibt** (Test mit 2/4/8 ok).
- Veröffentlichung: neues Repo ohne Upstream-Verlauf, Credits Pflicht, erst kurz vor dem Release; bis dahin `windows-fibo`.
- Reihenfolge: Easy Mode zuletzt (braucht L1, L2, Hide/Show aus L3). Easy-Mode-Ranking Fill: Qwen, Fibo; Expand: MOSS, Flux 2, Fibo, Qwen; `easymode.py`, Favorit aus dem Rechtsklick überschreibt.
- Rechtsklick auf Modell-Tab: Favorit, Tab ausblenden, Workflow-JSON speichern.
- Minimize = Einklappen zur Titelleiste (hide/show). Undo/Redo mit seiner `undo.png` (Redo gespiegelt).
- Krea-Styles bis 50 per Bildauswahl, Prompt-Templates per Klick; Tutorial-PSDs mit Testbild; Tooltips bei jedem Start.
- OpenFill-Ideen (`ideas.md`): T1 PhotoCraft-Befehle prüfen, T2 Seam-Korrektur als A/B, T3a Live-Vorschau, T3b Verlauf der letzten 20 Läufe, T4 Modell-Manager vergleichen; kein Varianten-Picker.
- Masken-Vergleichsbild gesehen; Umsetzung (Option A) noch nicht freigegeben.
- Branches: vor jedem Löschen fragen.

## 6. Aufgaben für den nächsten Chat (Rückmeldung des Nutzers vom 26.10., 22:00)
Jede Aufgabe auf eigenem Branch, Optionen vorher nennen, wo Design oder Wortlaut zu wählen ist. Screenshot des Fensters liegt dem Nutzer vor (er kann ihn erneut einfügen).

1. **Icons im ganzen Fenster** (mit `icons.py`, gleicher Stil wie die Slot-Icons; nicht zu groß, aber deutlich größer als jetzt; erst ein Vorschaublatt zeigen):
   - „+ Add“ bei *Extra LoRAs*: ein schönes Plus-Icon.
   - Zahnrad (Settings, Fußzeile rechts): „hässlich“, ein richtiges Zahnrad.
   - Undo/Redo neben Generate: schönere Pfeile (seine `undo.png` als Vorlage oder Vektor, Redo gespiegelt).
   - Auf/Ab-Pfeile der Zahlenfelder (Spinboxen: Seed, Variants, Steps, CFG, Denoise, Base res., Context, Mask grow/blur).
   - Ausklapp-Dreiecke bei *Negative prompt*, *Advanced* und überall, wo derselbe vorkommt (Chevron).
   - Alle übrigen Icons durchsehen: Kopier-Icon neben *LLM prompt enhancement*, Speichern/Papierkorb (`icon_image` in `gui_common.py`, noch 16-px-Pixel-Art).
2. **Slider wie in PhotoCraft** (Screenshot „Helligkeit“): dünne Spur, links hell gefüllt, rechts dunkel, runder weißer Knopf, Wert rechts in einem Kästchen. Heute: ttk-Scale mit gestreiftem orangem Griff („nicht ordentlich“). Betrifft *Sharpen result* und alle anderen Regler (Mix, LoRA-Stärke, Feather, Match …).
3. **Design-Vorschläge für minimale Verbesserungen** (Vorschläge des Vor-Chats, mit dem Nutzer abstimmen):
   - Prompt-Feld: dicke Windows-Scrollleiste mit Pfeilen → `ThinScrollbar` wie beim Fenster.
   - Radiobuttons (Funktionen) sind winzige Punkte → runde Radios im PhotoCraft-Look, etwas größer; gesperrte Funktionen grau wie jetzt.
   - Checkbox *LLM prompt enhancement* zeigt `☒`/`□` als Zeichen → echte Checkbox im gleichen Stil.
   - Spinboxen: schmale Chevron-Pfeile statt der großen Doppelpfeile; Mausrad ändert den Wert.
   - Gesperrte Felder (Context, Mask grow/blur bei Edit, Denoise) ausblenden statt grau zeigen, oder einheitlich ausgegraut mit Tooltip „gilt nur für Fill/Remove“ (Option).
   - *Image and mask* hat als einzige Gruppe einen Rahmen → einheitlich (Trennlinie mit Überschrift wie bei *Advanced*).
   - Oranger Tipp-Text unter dem Prompt sehr präsent → gedämpft (MUTED) mit kleinem Info-Icon; Orange nur für Aktionen/Fehler.
   - Fortschrittsbalken bleibt nach „Done“ voll orange → nach Abschluss dünn/neutral oder ausblenden.
   - Einheitliche Abstände (Raster 4/8 px), gleiche Höhe für Combobox und Spinbox.
   - Fußzeile: siehe 6.7.
4. **Drop auf ein gefülltes Slot-Bild ersetzt es** (kein neuer Slot). Heute ist nur `f_refs` als Ganzes Drop-Ziel (`_refs_setup_dnd`, `_refs_on_drop` → `_refs_add_paths`). Lösung: jeden Slot (`box`) als eigenes Drop-Ziel registrieren; Drop auf Slot k → `refslots.replace(k, bild)`; Drop auf den leeren Slot/Rest → hinzufügen. Gilt auch für mehrere Dateien (erste ersetzt, Rest hängt an? → Nutzer fragen).
5. **Kein leerer „free“-Platzhalter**: Es soll nur gefüllte Slots und genau einen leeren mit „Drop a picture or Ctrl+V“ geben. Ursache: `_refs_visible` zeigt bei Modellen mit ≤ 3 Slots immer alle (`return rs.max_refs`); richtig ist `min(max_refs, len(items) + 1)` für alle Modelle (Zeilen bleiben bei 3 je Reihe). Test in `test_refslots_gui.py` anpassen.
6. **„Add file“ zeigt das Plugin kurz doppelt/verstümmelt**: `_refs_add_file` ruft `filedialog.askopenfilenames` ohne `parent`. Das Fenster gehört per Winlink zu PhotoCraft (owned window), der Dialog hängt am falschen Besitzer, Tk zeichnet neu. Erst nachstellen, dann `parent=self.root` setzen; falls nötig Winlink-Watchdog während des Dialogs pausieren (`_link_job`) und danach `_try_link`.
7. **Refresh und Reset**: kleiner machen und klarer benennen. Heute: *Refresh* liest PhotoCraft/ComfyUI neu (Verbindung, LoRAs, Sampler, Workflows); *Reset* setzt Tab und Funktion auf die Startwerte. Zwei verschiedene Dinge, darum nicht einfach vereinen. Vorschläge (Nutzer wählt):
   - A (empfohlen): *Refresh* wird ein kleines ⟳-Icon direkt neben den Status-Punkten „PhotoCraft ● ComfyUI ●“ (Tooltip „Reconnect and reload models“); *Reset* wird ein kleiner Text-Button „Defaults“ (Tooltip „Back to this function's start settings“).
   - B: ein Menü-Knopf „⋯“ mit beiden Einträgen.
   - C: beide als kleine Icons (⟳ und ↺) mit Tooltips.
   - Reset ins Zahnrad-Menü verschieben wäre D.
8. **Strg+Z / Strg+Y bzw. Strg+Shift+Z** wie Undo/Redo-Button (Photoshop-Belegung: Strg+Z Undo, Strg+Shift+Z Redo). Achtung: im Prompt-Feld hat Strg+Z heute die Text-Rückgängig-Funktion von Tk. Optionen: A (empfohlen) im Textfeld bleibt Strg+Z Text-Undo, sonst Plugin-Undo; B immer Plugin-Undo. Binden an `self.root` mit Prüfung des Fokus-Widgets (wie `_refs_ctrl_v`).
9. **Alle Direktlinks zu den Modellen finden (WICHTIG)**: `manifest.py` hat 24 Dateien, 17 mit Link, 7 ohne. Für jede Datei den direkten Download-Link (Hugging Face `resolve/main/...` bzw. Civitai-Download-URL), Lizenz, Größe, ob gated. Quellen: Shipping-Addendum im Claude-Projekt, Hugging Face, Civitai. Ergebnis in `manifest.py` (Feld `url`) und als Tabelle in `docs/`. Recherche per Web; keine Downloads ohne Erlaubnis.
10. **Krea 2 Expand auf zwei Seiten liefert Sprünge und fremde Inhalte**, einseitig ok. Befund: `krea2-turbo-inpaint.json` ist ein reines Text-zu-Bild-Modell (Turbo, 8 Steps, CFG 1) mit `SetLatentNoiseMask` + `DifferentialDiffusion` bei Denoise 1; es bekommt das Original nur über die Rauschmaske, nicht als Bild-Bedingung (kein ReferenceLatent/Inpaint-Conditioning). Bei zwei Seiten ist die neue Fläche ein großes L mit wenig zusammenhängendem Kontext; ein destilliertes 8-Step-Modell hält das nicht zusammen. Also: für mehrseitiges Expand nicht geeignet. Optionen: A (empfohlen) Expand bei Krea 2 nur einseitig erlauben, mehrseitig automatisch in Runden (eine Seite nach der anderen, gleicher Seed); B wieder abschalten; C Hinweis im Tooltip, sonst nichts.
11. **Flux 3 Expand** funktioniert jetzt (Nutzer vermutet die höheren Steps, Fenster zeigte 15). Prüfen, mit welchen Steps es lief (`runs.jsonl`, `last-graph.json`), und den Startwert für Flux 3 Expand in `models.py` passend setzen; Entscheidung des Nutzers, ob es an bleibt.
12. **Masken-Option A** (siehe Abschnitt 4) und **Seam-Korrektur T2** warten auf Freigabe.

## 7. Befunde zum Weitergeben
- **Gleicher Seed, anderes Bild (Flux 2, Flux2Scheduler):** Die zwei Läufe um 21:42 hatten denselben Graphen; nur das Eingangsbild war anders. Edit schickt das sichtbare Dokument, und nach Lauf 1 lag dessen Ergebnis als sichtbare Ebene obenauf. Gegenprobe für den Nutzer: Generieren, Undo, gleicher Seed noch einmal. Flux2Scheduler ist laut Nutzer der beste der drei getesteten.
- **Branches löschen** ändert nichts am Code: Ein Branch ist nur ein Namensschild für einen Stand. Nach dem Merge steckt alles in `next`; ohne Löschen wird nur die Liste länger. `git branch -d` verweigert das Löschen, solange etwas nicht gemergt ist.

## 8. Live-Tests, die noch offen sind
- Neuer Nutzer: `photocraft-ai neuer-nutzer.bat`, Varianten 1 bis 4 (Startzustände, Einstellungen ohne Modelle).
- Flux 2 Text-to-Image mit und ohne Enhancer.
- Scrollbalken im echten Betrieb (Advanced offen, Qwen mit vielen Slots, 150 %).
- Beschreiben: erste Zeile, Ersetzen, von Hand geänderte Zeile bleibt.
- Flux-3- und Krea-2-Expand nach den Änderungen aus 6.10/6.11.
Bestätigt: Slot-Icons, Tags beim Modellwechsel, Qwen 2/4/8, Zahnrad/Fußzeile bei 380 px, Tab-Farben, Einstellungsfenster beim Schließen von PhotoCraft, 150 % Skalierung, Tipp-Text, zentrierter Tag, Flux-2-Scheduler-Auswahl.

## 9. Danach (Plan)
1. Aufgaben aus Abschnitt 6 (Reihenfolge mit dem Nutzer klären; Vorschlag: 5, 6, 4, 9, dann 1–3 als ein UI-Durchgang, dann 7, 8, 10, 11).
2. **L3 Fenster-Politur**: Hide/Show (Einklappen zur Titelleiste), Rechtsklick-Menü auf Tabs (Favorit, ausblenden, Workflow-JSON speichern), „Copy canvas to clipboard“, alten Knopf „Insert reference image“ entfernen (prüfen, ob noch sichtbar). Icons und Slider aus 6.1/6.2 gehören dazu.
3. OpenFill-Ideen (T1 PhotoCraft-Befehle, T3a Live-Vorschau, T3b Verlauf, T2 Seam-Korrektur).
4. Flux-3-Boxen (Entscheidung offen: A Textlauf von `Flux3LayoutPrompt` zuerst, B Knoten in den Workflow, C nur von Hand; Notizen `docs/flux3-bbox-workflow-notes.md`).
5. L4 Inhalte (Krea-Styles, Tipps, Tutorial-PSDs), dann **Easy Mode** zuletzt.
6. Vor dem Release: neues Repo, Credits (Upstream, Lucide-Icons, Modelle), README-Windows, Release-Prüfung auf 16 GB. Offen: `photocraft-ai.bat` auf 0.15.1 angleichen?
