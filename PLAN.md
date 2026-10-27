# PLAN: PhotoCraft x ComfyUI plugin, release 1

Stand 2026-10-27 (abends). Der Plan ist freigegeben. Abschnitt 3 ist die Arbeitsliste in ihrer Reihenfolge: von oben nach unten abarbeiten. Gesamtstand, Befunde und Optionen im Detail: `docs/HANDOFF-claude-code.md`. Die OpenFill-Ideen stehen ausführlich in `ideas.md` (Aufgaben T1 bis T4); hier sind sie eingeplant. Backup: Tag `backup-2026-10-26` (6df02df) und das ZIP des Users.

## 1. Erledigt (in `next`)

- Phase 0 (Aufteilung von `gui.py` in Mixins, `clipboard.py`, Test-Runner), L1 (Modell-Erkennung, Zahnrad-Fenster, Preflight, graue Tabs), L2 (Multi Image Edit mit Slots, Drag and Drop, Strg+V, Ausschneiden mit BiRefNet, Beschreiben mit Qwen 3.5 9B).
- UI-Runde 26./27.10.: Icons, PhotoCraft-Slider, Undo/Redo-Knöpfe, Papierkorb am Prompt, Knopfzeile über dem Prompt, Downloadlinks im Zahnrad-Fenster.
- Liste A vom 27.10. (Abstände, Chevron, „Custom LoRAs:“, ComfyUI-Punkt grün/rot, Slider rechts in einer Spalte und eintippbar, „Advanced settings“) und die Nachrunde: Ergebnis über einer Korrekturebene (vom User bestätigt), Flux 2 Refine startet auf „Default“, Leerzeile nach dem letzten LoRA weg, Qwen ohne Turbo, Expand/Edit getauscht, kürzere Slider-Texte.
- Einzelheiten: `git log next` und Handoff, Abschnitt 4.

## 2. Entscheidungen des Users (gelten weiter)

- Release 1: nur 16 GB getestet (int8-ConvRot-Dateien), 8-GB-Empfehlungen nur als Doku, nur Windows. AusBoss bleibt als Abhängigkeit.
- Veröffentlichung: neues Repo ohne Upstream-Verlauf, Credits Pflicht, erst kurz vor dem Release; bis dahin `windows-fibo`.
- Easy Mode zuletzt. Ranking Fill: Qwen, Fibo. Ranking Expand: MOSS, Flux 2, Fibo, Qwen. „Favorit“ aus dem Rechtsklick überschreibt es je Funktion.
- Rechtsklick auf Modell-Tab: Favorit, Tab ausblenden, Workflow-JSON mit allen Settings speichern. Minimize = Einklappen zur Titelleiste („hide“/„show“).
- Fill für Flux später. Krea 2 Expand und Flux 3 Expand sind zum Testen an; Entscheidung steht aus (Abschnitt 3, E).
- Remove: nur der Tipp unter dem Prompt, keine automatische Prompt-Ergänzung.
- Tooltips bei jedem Start. Krea-Styles: bis 50 per Bildauswahl, Prompt-Templates per Klick. Tutorial-PSDs nur mit Testbild.
- Strg+Z/Strg+Y bleiben wie heute (kein Plugin-Kürzel). Fast Mode gestrichen.
- Screenshots des Fensters nur, wenn der User etwas nicht selbst prüfen kann.

## 3. Arbeitsliste (Reihenfolge)

Jede Aufgabe auf eigenem Branch; wo Design oder Wortlaut zu wählen ist, vorher Optionen nennen. Details und Optionen je Punkt: Handoff, Abschnitt 6.

**B. Wichtig**
1. **Feste Startposition** (B.11): Das Plugin startet nach dem PhotoCraft-Start oft zu weit links oben; Drag and Drop nach unten lässt das Fenster dann kurz verschwinden. Zuerst mit dem User nachstellen, dann Optionen (feste Ecke im PhotoCraft-Fenster / letzte Position, auf den Bildschirm begrenzt).
2. ~~**Flux 2 Klein 9B ohne Quelle** (B.12)~~: **erledigt 27.10.** Die obsxrver-Fassung (`flux-2-klein-9b_int8_convrot.safetensors`) liefert im A/B-Test gleichwertige Bilder bei gleichem Tempo; Workflows und Download-Liste nutzen jetzt sie (Entscheidung des Users: Option B). Die alte Datei bindet der User später über C.13 ein.

**C. Neue Funktion**
3. **Eigene Datei statt Modell** (C.13), als Nächstes: Im Zahnrad-Fenster neben jeder Modell-Datei ein Knopf („Use my own file…“ empfohlen), Auswahl aus ComfyUIs Dateiliste des passenden Ordners.

**D. Recherche (nichts bauen, Ergebnis vorlegen)**
4. **Funktionen zuerst, Modell darunter?** (D.15): Folgen für die UX, Optionen, Empfehlung.
5. **UI-Fonts** (D.16): drei Vorschläge mit Lizenz, Windows-Verfügbarkeit, Tk-Tauglichkeit.
6. **PhotoCraft-Befehle prüfen** (OpenFill T1): Tabelle „Befehl → gibt es ihn → Folge für uns“ (Feather-Vorschau, Snapshots als ein Undo, Gruppen für Varianten, Crop über den Rand). Gegen die PhotoCraft-Version prüfen, die der User nutzt (0.15.1; ein Starter für 0.16 liegt im Repo-Ordner, ungetrackt).

**E. Offen aus der alten Liste**
7. **Refresh/Reset** kleiner und klarer: A ⟳-Icon neben dem ComfyUI-Punkt + „Defaults“ als Textknopf (empfohlen), B Menü „⋯“, C zwei Icons, D Reset ins Zahnrad.
8. **Expand-Entscheidungen:** Krea 2 Expand mehrseitig (A einseitig, mehrseitig in Runden; B abschalten; C nur Tooltip); Flux 3 Expand: Steps prüfen und Startwert setzen, bleibt es an?
9. **Ränder bei Fill/Expand:** Masken-Option A (wartet auf Freigabe) und **Seam-Korrektur als A/B-Test** (OpenFill T2: ein Lauf liefert „roh“ und „korrigiert“ als zwei Ebenen; Schalter standardmäßig aus, bis bestätigt).
10. **Restliche Design-Vorschläge:** Prompt-Feld mit dünnem Scrollbalken, runde Radios und echte Checkbox im PhotoCraft-Look, gesperrte Felder einheitlich, „Image and mask“ ohne Rahmen, Tipp-Text gedämpft mit Info-Icon, Fortschrittsbalken nach „Done“ neutral.

**L3 Fenster-Politur**
11. Hide/Show (Einklappen zur Titelleiste), Rechtsklick-Menü auf Tabs (Favorit, ausblenden, Workflow-JSON speichern), „Copy canvas to clipboard“, alten Knopf „Insert reference image“ entfernen, falls noch sichtbar.

**F. OpenFill-Ideen (aus `ideas.md`)**
12. **Live-Vorschau** unten im Plugin (T3a): ComfyUI mit `--preview-method taesd`, Frames über den Websocket; Layout-Optionen (immer reserviert / nur während des Laufs / Klick vergrößert).
13. **Verlauf der letzten 20 Läufe**, Lauf erneut laden (T3b): Ort, Umfang (nur Prompt oder alle Einstellungen, Seed fest oder neu) mit dem User klären.
14. **Modell-Manager von OpenFill vergleichen** (T4): sobald der User das Repo geladen hat; Ergebnis als Gegenüberstellung mit Empfehlung (übernehmen / anpassen / weglassen).

**Danach**
15. **Flux-3-Boxen** (Entscheidung offen: A Textlauf von `Flux3LayoutPrompt` zuerst, B Knoten in den Workflow, C nur von Hand; Notizen `docs/flux3-bbox-workflow-notes.md`).
16. **L4 Inhalte:** Krea-Style-Chooser, Tipps, tägliche Tooltips, Tutorial-PSDs.
17. **Easy Mode** (`easymode.py`), braucht Hide/Show aus L3.
18. **Release:** neues Repo, Credits (Upstream, Lucide-Icons, Modelle, Danrisi), README-Windows, Prüfung auf 16 GB; `photocraft-ai.bat` auf die aktuelle PhotoCraft-Version angleichen?

**Geparkt** (vom User nicht entschieden, aus `ideas.md`): Expand-Warnung über 25 % je Seite und automatische Runden; schnelles Remove mit LaMa (GPL-3.0, nur als Abhängigkeit); ComfyUI automatisch starten/herunterladen; Gerät beim Start loggen, „Open log folder“. Verworfen: Varianten-Picker, Cancel/Undo neu bauen.

## 4. Git-Ablauf (du musst nichts davon bedienen)

- `next` ist der Integrationsstand, den du testest. `windows-fibo` ist der zuletzt abgenommene Stand; nach deiner Abnahme wird er auf `next` vorgezogen.
- Je Aufgabe ein Branch (`feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`) aus `next`. Vor dem Zusammenführen laufen alle Tests (`python tests/run_all.py`), dann Merge in `next`. Nie pushen, nie Verlauf umschreiben, vor dem Löschen eines Branches fragen.
- Commits nach Conventional Commits, Details in `CLAUDE.md`.
- Altlast: `lanes/L1`, `lanes/L2` (eigene Klone, ignoriert, nicht mehr benutzt); Archiv `docs/archiv-lanes/`.

## 5. Risiken und offene Punkte

- „Workflow-JSON speichern“: unsere Workflows sind API-Format. Ob dein ComfyUI-Frontend es per Drag and Drop lädt, ist ungeprüft; sonst braucht es eine Umwandlung ins Editor-Format.
- Krea-Style-Explorer: Lizenz des Repos und der Bilder vor dem Mitliefern klären.
- Lizenzen für den Release: Fibo 2.0 (CC BY-NC) und die FLUX.2-Dateien nur nicht-kommerziell; Lenovo UltraReal verlangt Nennung von Danrisi; Lucide-Icons (ISC) nennen.
- Scribble/Sketch, Remove-Prompt, Encoder-Tausch, Steps-Prüfung: Recherche- und Testaufgaben ohne Code (`docs/tests/`).
- PhotoCraft 0.16: Wenn du umsteigst, die Befehle aus Punkt 6 und den Start (`photocraft-ai 0.16.bat`) einmal gegen 0.16 prüfen.

## 6. Wann ein neuer Chat sinnvoll ist

- Wenn Regeln vergessen werden, Antworten sich wiederholen oder ein Chat sehr lang wird.
- Bei einem größeren Themenwechsel (z. B. nach L3). Die neue Sitzung liest `CLAUDE.md`, `PLAN.md`, `docs/HANDOFF-claude-code.md` und bei den OpenFill-Punkten `ideas.md`.
