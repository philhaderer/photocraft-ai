# PLAN: PhotoCraft x ComfyUI plugin, release 1

Stand 2026-10-30. Der Plan ist freigegeben. Abschnitt 3 ist die Arbeitsliste in ihrer Reihenfolge: von oben nach unten abarbeiten.

**Welche Datei wofür:**
- `PLAN.md` (diese Datei): was auf deinen Test wartet, deine Entscheidungen, was offen ist.
- `docs/erledigt.md`: was wann gebaut wurde (Verlauf, nach Datum).
- `docs/HANDOFF-claude-code.md`: Technik für die nächste Sitzung (Umgebung, Prüfen ohne GPU, Befunde).
- `ideas.md`: die offenen OpenFill-Ideen im Detail (T3b, T4, Geparkt).
- `CLAUDE.md`: Arbeitsweise und Regeln.
- `user-edits.md`: wo Texte stehen, die du selbst ändern kannst, und was du danach sagst.
- `docs/archiv/`: alte Fassungen und fertige Recherchen (PLAN vom 29.10., Handoff vom 28.10., UX-Studie, Schriften, L1/L2).

## 1. Wartet auf deinen Live-Test

Alles gebaut und in `next`, mit Tests; im echten Fenster noch nicht von dir geprüft. (Live-Test vom 30.10. bestanden: Fill-Maske, Verlauf, Punkt 11 und 12, Describe, Seam-Korrektur, Fensterkopf, Slots, Zahnrad-Fenster; Liste in `docs/erledigt.md`.)

**Neu vom 31.10.**
- **Zahnrad-Fenster mit Reitern je Modell:** oben „Models“ und „Credits“; in „Models“ stehen „Linked files“ (Infotext, Undo, Reset) und darunter ein Reiter je Modell (Zustandszeichen im Titel) plus „Additional“. Jeder Modellreiter: Haken „Show this model in the plugin“, „Covers these modes:“ (grün bereit, rot Dateien fehlen, grau nicht angeboten) und die Dateien. Dateien, die das Plugin nicht selbst lädt (gesperrt bei Hugging Face, Civitai), tragen einen orangen Hinweis; „alle fehlenden“ nennt sie im OK-Fenster und öffnet ihre Seiten im Browser. Downloads laufen parallel (keine Warteschlange); die TAESD-Decoder kommen von `raw.githubusercontent.com`, weil `github.com` in Windows-Python am Zertifikat scheitert.
- **Download-Knöpfe (14c Schritt 5):** Disk-Symbol je Datei und „alle fehlenden“ je Modell, mit OK-Fenster, Balken und Abbrechen; Testlauf ohne Verschieben: `PCCOMFY_MODELS_DIR=<Testordner>` setzen (dann landet alles dort). Dein ComfyUI listet die Vorschau-Decoder nur, wenn in der `extra_model_paths.yaml` die Zeile `vae_approx` nicht auskommentiert ist (nicht verändert).
- Zahnrad-Fenster: „Linked files“ mit Undo und Reset stehen oben, direkt unter den Modell-Haken; die Haken tragen die vollen Namen (drei pro Zeile); das Fibo-Modell heißt überall „Fibo 2.0 Edit Turbo“ (Ebenennamen in PhotoCraft z. B. „Fibo 2.0 Edit Turbo Fill Selection 3“, bei Edit ohne doppeltes „Edit“).
- `downloads.py` (14c Schritt 4) ist da und getestet, hängt aber noch an keinem Knopf.

**Neu vom 30.10. (abends)**
- **Zahnrad-Fenster, Schritt 3 von 14c (31.10.):** Das Ketten-Symbol öffnet an der Datei eine Liste der Dateien, die ComfyUI für diese Art hat (ähnlichster Name zuerst, Haken am verknüpften, „Unlink“ ganz unten); ein Klick verknüpft sofort. Undo und „Reset to startup“ stehen in der Kopfzeile von „Linked files“. Die Dateien jedes Modells sind nach Art sortiert (Diffusion, Text-Encoder, VAE, LoRA, Rest). Die `extra_model_paths.yaml`-Funktion ist entfernt (ComfyUI listet Standardordner, YAML-Ordner und Symlinks selbst); beim Öffnen des Fensters liest das Plugin ComfyUIs Listen neu.
- **Zahnrad-Fenster, Schritt 1 und 2 von 14c:** Zeilen statt Textfeld, Pfad mit Ordner, Größe, Disk-Symbol (öffnet vorerst nur den Download im Browser, Rechtsklick kopiert den Link), Ketten-Symbol (seit Schritt 3 mit Auswahlliste); Modell-Haken in einer Reihe; Fenster startet breiter und merkt sich seine Größe; „Additional models“ mit BiRefNet und den Vorschau-Decodern.
- **Live preview** ist aus und ausgegraut, solange der Vorschau-Decoder des Modells fehlt. Bei dir fehlen alle drei (zusammen 63 MB): die Vorschau ist also vorerst überall aus, bis die Dateien da sind.
- **LLM-Zeile** nur noch, wo ein Textmodell schreibt; Fibo Text to image mit LLM (startet aus).

**Neu vom 30.10. (Nachmittag)**
- **LLM-Zeile unter dem Prompt:** „LLM prompt enhancement“ steht überall direkt unter dem negativen Prompt, über Upscale factor und LoRA-Schaltern; ohne Modellnamen (der steht nur im Tooltip). Turbo-/LoRA-Haken bündig links. Seit 30.10. abends nur noch dort, wo ein Textmodell den Prompt schreibt (nie ausgegraut); Defaults und erster Start setzen den Haken auf aus.
- **Fibo Text to image mit LLM** (30.10. abends): derselbe Schreiber wie Fibo Edit (Qwen 3.5 9B int8 ConvRot) mit Brias offiziellem „Generate“-Systemprompt; startet aus. Blindtest gelaufen: Haken startet aus, bleibt verfügbar.
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
- **14a Qwen-Encoder-Blindtest (erledigt):** 6 Paare, alle „gleich gut“; der Edit-Workflow nutzt jetzt `qwen3vl_8b_int8_convrot`, `qwen3vl_8b_fp8_scaled` ist aus Manifest und Downloadliste raus (10,6 GB weniger). Nur Edit wurde geprüft, ein Seed je Bild; Fill, Expand, Remove und Multi Image Edit laufen mit demselben Encoder, wurden aber nicht einzeln getestet.
- **14b Prüfsummen ins Manifest (erledigt 30.10.):** SHA-256 jeder Datei aus der Hugging-Face-API (`?blobs=true`) bzw. Civitai, ohne Download; ein Test prüft, dass jede Datei mit Link eine Prüfsumme und Größe hat. Grundlage für 14c.
- **14c Zahnrad-Fenster neu und Downloads** (entschieden 30.10. abends, Option 1: echte Zeilen statt Textfeld). Branches in dieser Reihenfolge:
  1. **(gebaut 30.10.) Fenster-Umbau:** startet ca. 760 px breit, Breite und Höhe werden beim Schließen gemerkt; Kopfzeile „Enable models in plugin“ links, die sechs Modell-Haken in einer Reihe (später der VRAM-Knopf aus 14d dazu); je Modell ein Block, je Datei eine Zeile mit festen Spalten: Haken, Pfad mit Ordner (`/diffusion_models/…`, `/loras/Flux 3/…`, bei Verknüpfung „(your file: …)“), Größe, Symbole. Geteilte Pflichtdateien (flux2-vae, qwen3vl_4b) bleiben bei jedem Modell mit „also used by …“; die LLM-Dateien bleiben bei ihren Modellen.
  2. **(gebaut 30.10.) Abschnitt „Additional models“:** nur BiRefNet (Cut out in Multi Image Edit) und die Vorschau-Decoder (taef2: Flux 3, Flux 2, Fibo, MOSS; taeqi: Qwen; lighttaew: Krea 2), je mit Verwendungszweck. Fehlt der Decoder des Modells, ist „Live preview“ aus und nicht klickbar, bis die Datei da ist.
  3. **(gebaut 31.10.) Ketten-Symbol statt „Choose another file“:** Liste an der Datei, ein Klick verknüpft sofort, „Unlink“ zuletzt; der Bereich „Use another file“ und die YAML-Funktion sind weg, Undo und Reset in „Linked files“. Dateien aus fremden Ordnern kennt nur ComfyUI selbst; den Zielordner für Downloads klärt Schritt 5: ComfyUI-Ordner automatisch aus dem laufenden Prozess suchen, sonst einmal per Ordner-Dialog fragen und merken (entschieden 31.10.).
  4. **(gebaut 31.10.) `downloads.py`** nur mit der Python-Standardbibliothek: `.part`-Datei, Fortsetzen nach Abbruch (HTTP Range), Größe und SHA-256 prüfen, erst dann umbenennen; freien Platz vorher prüfen; Abbrechen.
  5. **(gebaut 31.10.) Disk-Symbol statt „download“:** Klick auf das Disk-Symbol einer Datei oder im Modellkopf („alle fehlenden“) fragt mit OK (Datei, Größe, Zielpfad) und lädt dann in den `models`-Unterordner der Art; Balken und ✕ in der Zeile, Warteschlange. Den Ordner findet `comfydir.py` über den ComfyUI-Prozess am Port, sonst fragt das Fenster einmal; `PCCOMFY_MODELS_DIR` lenkt zum Testen um. Gesperrte Hugging-Face-Dateien (Flux 3 Klein) und Civitai öffnen vorerst nur die Seite (bis Schritt 6); Rechtsklick kopiert den Link. Nach dem Laden steht „restart ComfyUI“ an der Zeile, bis ComfyUI die Datei listet.
  6. **(gestrichen 30.10., deine Entscheidung) Hugging-Face-Token-Panel** für gesperrte Dateien (Flux 3 Klein, Upsampler): 4 Schritte wie OpenFill (Seite öffnen, Lizenz annehmen, Token anlegen, einfügen); Token nur an huggingface.co, nie im Log.
  Danach Hinweis „ComfyUI neu starten“, falls ComfyUI die neue Datei nicht selbst sieht (prüfen: neuere ComfyUI-Versionen lesen einen Ordner neu, wenn er sich geändert hat).
- **14d VRAM-Knopf** (Zahnrad; auf später verschoben, 30.10.): VRAM aus ComfyUI (`/system_stats`), RAM und freier Platz aus Windows; je Modell „läuft gut / langsamer (Systemspeicher) / zu groß“ nach OpenFills Rechnung (größte Modelldatei + 1,5 bis 2,5 GB; Text-Encoder laden nacheinander). Nur 16 GB ist gemessen, alles andere steht als „geschätzt“ da. **Entschieden 30.10.:** Knopf „16 GB VRAM“ oben im Zahnrad-Tab „Models“; ein Klick klappt eine Liste je Modell auf (läuft gut / langsamer / zu groß), die Zahlen stehen im Tooltip.
- **Vor 14e: Feinschliff-Liste (von dir am 30.10., Reihenfolge nach Branches; Vorschläge von mir stehen mit „Vorschlag“, Entscheidung offen)**
  1. **(gebaut 30.10., `feat/polish-texts`) Texte:** ohne gewählte Funktion/Modell (neuer Nutzer) „Choose a model“ statt „choose a function“; „Upscale factor“ (statt „upscale by factor“) in der Schriftgröße der anderen Texte (z. B. „Ultra real LoRA“); „Edit whole image“ heißt überall „Edit Canvas“; „Defaults“ unten heißt „Set Page to Defaults“, Knopfstil wie „Show feather“, setzt nur die aktive Funktion und das aktive Modell zurück (z. B. nur Expand Image und Fibo).
  2. **(gebaut 30.10., `feat/polish-sizes`) Kleine Maße:** alle Pfeile wie bei Steps auf 90 % und 2 bis 3 px Abstand; Eingabefelder Steps und CFG gleich breit, gerade für zwei Ziffern; Seed-Feld ca. 80 % der jetzigen Breite (so breit wie der Text darüber); Undo/Redo rechtsbündig, der Rest der Zeile links; Anzahl der Generierungen auch bei 1 anzeigen („x1“).
  3. **(gebaut 30.10., `feat/history-list`) Verlauf:** Verlauf (History) scrollbar mit Mausrad und Scrollbalken, erste Zeile „Erase history“ löscht ihn. (Einzelklick auf den Kopf gestrichen: der Minimieren-Knopf genügt.)
  4. **(gebaut 30.10., `feat/live-preview-footer`) Live preview:** Schalter neben „Defaults“ (bzw. „Set Page to Defaults“), ausgegraut, wenn der Vorschau-Decoder des Modells fehlt; Höchsthöhe für Hochformat. Umgesetzt: höchstens 300 px hoch (mit Fenster-Maßstab, `gui_common.PREVIEW_MAX_H`), nie über 35 % der Bildschirmhöhe; Hochformat wird schmaler, Querformat bleibt fensterbreit.
  5. **Statuszeile:** Prozesse kurz nennen, bei mehreren Runden „x/x“ (Upscale-Tiles, Steps). Vorschlag, was dauert genug: Modell laden, LLM schreibt den Prompt (ca. 20 s), Sampling mit Schritt x/n, Upscale-Kacheln x/n, Ergebnis in PhotoCraft platzieren; nicht anzeigen: Ebenen exportieren, Maske bauen (unter etwa 2 s).
  6. **Tastatur und Defaults:** Strg+Alt+Enter bricht einen Lauf ab; Fibo Refine startet mit Sharpening 10 %.
  7. **(gebaut 30.10., `feat/llm-describe-button`) Neuer Knopf „LLM“ (Bild beschreiben):** links neben „Delete prompt“; beschreibt das aktuelle Canvas-Bild und hängt den Prompt nach einem Zeilenumbruch ans Ende der Prompt-Box. Soll dasselbe LLM nehmen, das das Modell schon benutzt (kein Zusatz-Download). Der Describe-Knopf (Expand, `describe-image.json`, Qwen 3.5 9B int8 ConvRot mit Bildeingang) gibt es schon. Vorschlag je Modell: Fibo: Qwen 3.5 9B int8 ConvRot (dort Schreiber); Qwen und MOSS: Qwen 3.5 9B w4a8 GPTQ (optional); Flux 2/3: Prompt-Upsampler (Qwen 3.5 9B w4a8, optional); Krea 2: Qwen3-VL 4B fp8 (dort Schreiber). Fehlt das Schreibermodell, Rückfall auf Qwen 3.5 9B int8 ConvRot, sonst Knopf grau. Entschieden 30.10. (so). Bildeingang geprüft 30.10.: alle fünf Modelle (Qwen 3.5 9B int8 ConvRot, w4a8 GPTQ, Flux-3-Upsampler, Qwen3-VL 4B fp8 und int8) beschreiben ein Foto.
  8. **Rechtsklick auf Modell-Chip:** Menü „Save current settings for this mode and model“, „Load default settings“, Favourite, Hide (in dieser Reihenfolge).
  9. **Modi ohne Pflicht-LoRA:** Modi, die mit den Standardeinstellungen keine LoRA brauchen (auch SeedVR2 bei Flux 3 Upscale), bleiben im Plugin aktiv und laufen; Fehlermeldung nur, wenn die Einstellung des Nutzers vom Standard abweicht; die Option ist grau, solange die LoRA bzw. SeedVR2 fehlt.
  10. **(gebaut 30.10., `feat/auto-shortcut`, Variante A) Start-Verknüpfung automatisch; Vorschläge waren:** A: `setup-windows.bat` legt sie am Ende an (sucht `photocraft.exe` in `C:\programs\photocraft-*`, `Program Files`, `Downloads`, sonst Ordner-Dialog). B: beim ersten Start des Fensters fragt ein OK-Fenster einmal „Desktop-Verknüpfung anlegen?“ (exe aus dem laufenden PhotoCraft-Prozess). C: Knopf „Create desktop shortcut“ im Zahnrad. Meine Empfehlung: A und C zusammen (Installation macht es einmal, der Knopf repariert es später).
  Fibo-LLM-Tooltip (erledigt 30.10., `fix/fibo-tooltip-vgl`): „Qwen 3.5 9B writes a detailed prompt. About 20 s extra.“; der alte Knoten-Hinweis `VGLBionic` ist aus dem Manifest entfernt. Das „About 20 s“ ist nicht neu gemessen.
- **14e Dateien am Kopf erkennen:** `.safetensors`-Kopf lesen (nur die Tensor-Liste, nie Pickle-Dateien), um umbenannte Dateien in „New file“ als Vorschlag zu markieren („sieht aus wie …“). Kleinster Nutzen, zuletzt.
- **Später (nach Release 1):** GGUF (Loader im Graph tauschen, ComfyUI-GGUF als Abhängigkeit) für 8-GB-Nutzer.

**LLM prompt enhancement (entschieden 30.10. abends)**
- **Fibo Text to image** hat den LLM-Schreiber (30.10. abends, Brias „Generate“-Systemprompt). Blindtest 30.10.: ohne LLM 9, mit LLM 4, gleich 11 von 24 (`docs/tests/fibo-t2i-llm.md`). **Entschieden:** Haken startet aus, bleibt verfügbar.
- **Später, je als Testrunde (blind, mit/ohne LLM):** Edit whole image (könnte mit LLM besser werden); Qwen Fill mit einem Prompt-Schreiber; Multi Image Edit bei Flux 3, Flux 2 und Qwen (dort ist der Haken heute ausgegraut).
- Ausgeblendet bleibt die Zeile bei Expand, Remove, Refine und Upscale (feste oder fertige Prompts) und überall, wo es (noch) kein Textmodell gibt.

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
