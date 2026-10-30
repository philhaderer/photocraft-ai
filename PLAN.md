# PLAN: PhotoCraft x ComfyUI plugin, release 1

Stand 2026-10-30. Der Plan ist freigegeben. Abschnitt 3 ist die Arbeitsliste in ihrer Reihenfolge: von oben nach unten abarbeiten.

**Welche Datei wofür:**
- `PLAN.md` (diese Datei): was auf deinen Test wartet, deine Entscheidungen, was offen ist.
- `docs/erledigt.md`: was wann gebaut wurde (Verlauf, nach Datum).
- `docs/HANDOFF-claude-code.md`: Technik für die nächste Sitzung (Umgebung, Prüfen ohne GPU, Befunde).
- `ideas.md`: die offenen OpenFill-Ideen im Detail (T3b, T4, Geparkt).
- `CLAUDE.md`: Arbeitsweise und Regeln.
- `docs/archiv/`: alte Fassungen und fertige Recherchen (PLAN vom 29.10., Handoff vom 28.10., UX-Studie, Schriften, L1/L2).

## 1. Wartet auf deinen Live-Test

Alles gebaut und in `next`, mit Tests; im echten Fenster noch nicht von dir geprüft. (Live-Test vom 30.10. bestanden: Fill-Maske, Verlauf, Punkt 11 und 12, Describe, Seam-Korrektur, Fensterkopf, Slots, Zahnrad-Fenster; Liste in `docs/erledigt.md`.)

**Neu vom 30.10. (Nachmittag)**
- **LLM-Zeile unter dem Prompt:** „LLM prompt enhancement“ steht überall direkt unter dem negativen Prompt, über Upscale factor und LoRA-Schaltern; ohne Modellnamen (der steht nur im Tooltip). Turbo-/LoRA-Haken bündig links.
- **Qwen Text to image** startet ohne LLM.
- **Zahnrad-Fenster:** „New file“ bietet die erwartete Datei nur noch an, wenn sie da ist; neu in der Liste: Restore-LoRA (Flux 3 Upscale, Pflicht), BiRefNet (Cut out, optional), UltraReal-LoRA für MOSS Text to image jetzt Pflicht.

**Älter (28.10.), noch nicht ausdrücklich bestätigt**
- **Mask density:** Regler in PhotoCraft 0.17+ (Fill startet seit 30.10. bei 100 %, Option A). Danach willst du ihn auch bei anderen Funktionen (z. B. Expand) ausprobieren.
- **Fibo Expand** mit neuem Satz („Replace the white area on the …“; im A/B 30 von 30 gefüllt).
- **Zahlenfelder:** Klick setzt den Cursor, Doppelklick markiert nur die Zahl, Pfeiltasten (0,05 bzw. 1 %), LoRA-Felder nur Zahlen, „%“ bleibt stehen.
- **Kleine Verbesserungen vom 28.10.:** Fibo-Sharpen-Startwerte (Refine 30 %, Text to image 20 %), Fibo Refine mit Default-Prompt und „Mix source/new image“, zweiter Satz im Fill-Tipp, Trennlinie über der Statuszeile, Zahnrad-Klick schließt das Fenster wieder, Zahnrad kleiner ohne dunklen Hintergrund, Denoise ausgeblendet, allgemeine Funktions-Tooltips.
- **Desktop-Verknüpfung** „PhotoCraft AI“ anlegen und testen: `python -m pccomfy shortcut --photocraft <photocraft.exe>`.

**Aus den ersten Sitzungen (26./27.10.), nie einzeln abgehakt:** neuer Nutzer (`photocraft-ai neuer-nutzer.bat`, Varianten 1 bis 4); Flux 2 Text to image mit und ohne Enhancer; Scrollbalken mit offenen Advanced settings und vielen Qwen-Slots bei 150 %; Wert-Kästchen tippen (Enter, Wegklicken); ComfyUI-Punkt grün/rot beim Beenden von ComfyUI. Was davon im Alltag schon funktioniert, kannst du einfach als erledigt melden.

## 2. Deine Entscheidungen (gelten weiter)

**Release und Ablauf**
- Release 1: nur 16 GB getestet (int8-ConvRot-Dateien), 8-GB-Empfehlungen nur als Doku, nur Windows. AusBoss bleibt Abhängigkeit.
- Veröffentlichung: neues Repo ohne Upstream-Verlauf, Credits Pflicht, erst kurz vor dem Release.
- Easy Mode zuletzt. Fast Mode gestrichen. PhotoCraft 0.16 ist seit 28.10. deine Hauptversion.
- Für Testungen (Modellvergleiche, Blindtests, neue Einstellungen) die Prompts aus `docs/tests/testprompts.md` (192 Prompts der ImageBench-Galerie).
- Screenshots des Fensters nur, wenn du etwas nicht selbst prüfen kannst.

**Modelle und Reihung**
- Ranking (in `models.RANKING`, zum Testen vorn in jedem Funktions-Tooltip): Fill und Remove: Fibo, Qwen. Expand: Flux 2, Flux 3, Qwen, Fibo. Offen: Text to image, Edit, Multi Image Edit, Upscale, Refine, dazu Flux 2/3 bei Remove. Der Favorit aus dem Rechtsklick überschreibt das Ranking je Funktion.
- Krea 2 und MOSS Expand sind seit 29.10. abgeschaltet (Blindtest: 2 und 10 von 64 gut), geparkt in `models.PARKED_EXPAND`. Flux 3 Expand läuft mit der Outpaint-LoRA. Fill für Flux später.
- MOSS Text to image: CFG 3.0, 35 Steps, ohne DMD2 (Blindtest 29.10.). Qwen startet ohne Turbo, Qwen-Slotzahl 8.

**Fenster**
- Kein Tooltip zur runden Auswahl (30.10.).
- Fensterkopf: Funktion zuerst (große Buttons mit Symbol), Modelle darunter als Chips. Minimieren = Einklappen zum Header (Knopf oder Doppelklick).
- Rechtsklick auf Modell-Chip: Favorit (Haken im Menü, kein Zeichen am Chip), Modell ausblenden; zurückholen nur im Zahnrad-Fenster. Workflow-JSON speichern verworfen.
- Settings-Fenster mit Tabs „Models“ und „Credits“; weitere Tabs später.
- Strg+Z/Strg+Y bleiben wie heute (kein Plugin-Kürzel). Tooltips bei jedem Start.
- Fortschrittsbalken bleibt orange. Runde Radios gibt es nicht (PhotoCraft hat keine), stattdessen kleine Schalter.

**Masken und Regler**
- Layer mask nur soft / hard / none. Fill Qwen/Fibo „soft“ = Auswahl voll deckend, weicher Rand nur außen, läuft bis zum Ausschnittrand aus (Option A, 30.10.); Mask density startet bei 100 %.
- Regler-Reihenfolge: Sharpen, Match colours, Context, Edge feather, Layer mask mit „Show feather“. „Image and mask“ ausgeblendet. Denoise ausgeblendet.
- Startwerte: Qwen Fill 0.4 / 4 %, Qwen und Fibo Remove 0.4 / 10 %, Fibo Fill Context 0.4. Jeder Start setzt den Startwert der Funktion (kein Merken).
- Kein eigener Modus für Rechteck und Lasso. Fibo mit glatter Auswahl bleibt, wie es ist. Referenz: Fibo, Rechteck, soft, 6,5 % Feather.
- Remove läuft einmal; nur der Tipp unter dem Prompt, keine automatische Prompt-Ergänzung.
- Reset setzt alles zurück außer aufgeklappten Bereichen und der Checkpoint-Datei.

**Ergebnis in PhotoCraft**
- Ergebnis ohne Zwischenablage, immer ganz oben; Varianten in einer Gruppe „<Funktion> <Lauf-Nr.>“; Feather-Vorschau als Quick Mask. Expand per Crop abgelehnt.
- Die zwei alten Kanäle `pccomfy-preview-…` in deinem zweiten „Untitled-1“ bleiben.

**Inhalte für später**
- Krea-Styles: bis 50 per Bildauswahl, Prompt-Templates per Klick. Tutorial-PSDs nur mit Testbild.

## 3. Arbeitsliste (Reihenfolge)

Jede Aufgabe auf eigenem Branch; wo Design oder Wortlaut zu wählen ist, vorher Optionen nennen. Die Punkte behalten ihre alten Nummern.

**Als Nächstes**
**Als Nächstes: Modell-Manager (Punkt 14, Vergleich `docs/openfill-modellmanager.md`)**, je Schritt ein Branch, in dieser Reihenfolge:
- **14a Qwen-Encoder-Blindtest** (gebaut 30.10., `tests/live_qwen_encoder.py`, 12 Läufe): laufen lassen (GPU, mit deiner Erlaubnis), du bewertest blind. Ist int8_convrot gleich gut: Edit-Workflow auf convrot umstellen, `qwen3vl_8b_fp8_scaled` fällt bei Qwen weg (10,6 GB weniger Download).
- **14b Prüfsummen ins Manifest:** SHA-256 jeder Datei aus der Hugging-Face-API (`?blobs=true`) bzw. Civitai, ohne Download; ein Test prüft, dass jede Datei mit Link eine Prüfsumme und Größe hat. Grundlage für 14c.
- **14c „Download all missing“ je Modell** (Symbol rechts vom Modell im Zahnrad, Tooltip mit der Größe): eigenes Modul `downloads.py` nur mit der Python-Standardbibliothek (keine neue Abhängigkeit): Download in eine `.part`-Datei, Fortsetzen nach Abbruch, Größe und SHA-256 prüfen, erst dann umbenennen; freien Platz vorher prüfen; Fortschritt und Abbrechen im Zahnrad-Fenster; danach Hinweis „ComfyUI neu starten“. Gesperrte Dateien (Flux 3 Klein, Upsampler): Panel mit 4 Schritten wie OpenFill (Seite öffnen, Lizenz annehmen, Token anlegen, einfügen); Token nur an huggingface.co, nie im Log. **Zu entscheiden:** Zielordner, Civitai-Datei (UltraReal).
- **14d VRAM-Knopf** (Zahnrad): VRAM aus ComfyUI (`/system_stats`), RAM und freier Platz aus Windows; je Modell „läuft gut / langsamer (Systemspeicher) / zu groß“ nach OpenFills Rechnung (größte Modelldatei + 1,5 bis 2,5 GB; Text-Encoder laden nacheinander). Nur 16 GB ist gemessen, alles andere steht als „geschätzt“ da. **Zu entscheiden:** wo und wie es angezeigt wird.
- **14e Dateien am Kopf erkennen:** `.safetensors`-Kopf lesen (nur die Tensor-Liste, nie Pickle-Dateien), um umbenannte Dateien in „New file“ als Vorschlag zu markieren („sieht aus wie …“). Kleinster Nutzen, zuletzt.
- **Später (nach Release 1):** GGUF (Loader im Graph tauschen, ComfyUI-GGUF als Abhängigkeit) für 8-GB-Nutzer.

**Offen aus den Testrunden**
- **Edge feather bei Fill** (du bist unsicher, 30.10.): später als Testrunde anlegen (z. B. 0 %, Startwert, doppelt; blind), auch ob 0 % wieder hart sein soll.
- **Ranking** für die noch offenen Funktionen (Abschnitt 2), wenn du es nennst.

**Danach**
15. **Flux-3-Boxen** (entschieden 30.10.: **A**, zuerst ein Textlauf von `Flux3LayoutPrompt`; Notizen `docs/flux3-bbox-workflow-notes.md`).
16. **L4 Inhalte:** Krea-Style-Chooser, Tipps, tägliche Tooltips, Tutorial-PSDs.
17. **Easy Mode** (`easymode.py`).
18. **Release:** neues Repo, Credits (Upstream, Lucide-Icons, Inter-Schrift (OFL), Modelle, Danrisi), README-Windows, Prüfung auf 16 GB; `photocraft-ai.bat` (zeigt noch auf 0.14.0) an die aktuelle PhotoCraft-Version angleichen. Start für andere Nutzer: Verknüpfung als Standard, Autostart als Schalter im Zahnrad prüfen (Code liegt bereit, Einzelheiten `docs/erledigt.md`, 28.10.). Am saubersten wäre ein Start durch PhotoCraft selbst (Einstellung `generatorEnabled`): bei den PhotoCraft-Entwicklern nachfragen.

**Geparkt** (von dir nicht entschieden, aus `ideas.md`): Expand-Warnung über 25 % je Seite und automatische Runden; schnelles Remove mit LaMa (GPL-3.0, nur als Abhängigkeit); ComfyUI automatisch starten/herunterladen; Gerät beim Start loggen, „Open log folder“; AnyPaint-LoRA für Krea 2.
**Verworfen:** Varianten-Picker, Cancel/Undo neu bauen, Workflow-JSON speichern, Expand per Crop, Fast Mode.

## 4. Git und Repo (du musst nichts davon bedienen)

- `next` ist der Stand, den du testest; `windows-fibo` der zuletzt abgenommene; `main` = Upstream. Regeln für Branches und Commits: `CLAUDE.md`.
- Nur eine Sitzung macht Git in diesem Ordner; weitere Sitzungen arbeiten in einem eigenen Worktree oder nur lesend.
- Privates Repo <https://github.com/philhaderer/photocraft-ai> (Remote `private`): `next` wird dort als `main` hochgeladen, nur auf deinen Wunsch. `origin` bleibt der Upstream. Zweiter Rechner: `docs/installation-zweiter-rechner.md`.
- Backups: Tag `backup-2026-10-26` (6df02df) und dein ZIP; Tag `vor-claude-code` (65e955f).

## 5. Risiken und Lizenzen

- Krea-Style-Explorer: Lizenz des Repos und der Bilder vor dem Mitliefern klären.
- Fibo 2.0 (CC BY-NC) und die FLUX.2-Dateien nur nicht-kommerziell; Lenovo UltraReal verlangt Nennung von Danrisi; Lucide-Icons (ISC) nennen; Inter (SIL OFL 1.1) liegt mit `OFL-Inter.txt` bei.
- Scribble/Sketch, Remove-Prompt, Encoder-Tausch, Steps-Prüfung: Recherche- und Testaufgaben ohne Code (`docs/tests/`).

## 6. Wann ein neuer Chat sinnvoll ist

- Wenn Regeln vergessen werden, Antworten sich wiederholen oder ein Chat sehr lang wird.
- Bei einem größeren Themenwechsel. Die neue Sitzung liest `CLAUDE.md`, `PLAN.md`, `docs/HANDOFF-claude-code.md` und bei den OpenFill-Punkten `ideas.md`.
