# Erledigt: was wann gebaut wurde

Verlauf nach Datum, neuester Stand oben. Alles liegt in `next`. Die vollen Texte von damals (Aufgaben, Befunde, Optionen) stehen in `docs/archiv/PLAN-2026-10-29.md` und `docs/archiv/HANDOFF-2026-10-28.md`, Einzelheiten zu jedem Commit in `git log next`. Was noch auf den Live-Test wartet, steht in `PLAN.md`, Abschnitt 1.

## 30.10.

- **Abends (Feedback des Users):** LLM-Zeile nur, wo ein Textmodell den Prompt schreibt, nie ausgegraut; aus bei Expand, Remove, Refine, Upscale; Defaults und erster Start: Haken aus (`fix/llm-row-hidden-where-prompts-exist`, `fix/llm-row-only-with-text-model`). Fibo Text to image mit LLM-Schreiber und Brias „Generate“-Systemprompt (`feat/fibo-t2i-llm`), Blindtest `tests/live_fibo_llm.py` (ohne LLM 9, mit 4, gleich 11 von 24; Haken startet aus, `docs/tests/fibo-t2i-llm.md`). Neuer-Nutzer-Start mit PhotoCraft 0.17 (`chore/new-user-photocraft-017`). Plan 14c für das neue Zahnrad-Fenster (`docs/model-manager-window-and-llm-tests`). 14c Schritt 1 Zeilen-Layout (`feat/settings-window-rows`) und Schritt 2 „Additional models“ und Live preview nur mit Decoder (`feat/settings-additional-models`).
- **Live-Test bestanden** (User 30.10.): Fill-Maske „bis zum Ausschnittrand“, Verlauf der letzten 20 Läufe, L3 Fenster-Politur (Punkt 11), Live-Vorschau (Punkt 12), Describe mit Zufalls-Seed, Seam-Korrektur je Modell, Flux 3 Expand mit Outpaint-LoRA, Fensterkopf und Fußzeile, kleinere Punkte vom 29.10., Slots, Zahnrad-Fenster (15a). Offen: Edge feather (Testrunde später).
- **Modell-Manager, erste Schritte** (Vergleich `docs/openfill-modellmanager.md`): „New file“ nur mit vorhandener Datei (`fix/relink-list-only-installed`); Restore-LoRA und BiRefNet im Manifest, AusBoss-LoRA-Liste wird geprüft und umbenannt (`fix/manifest-restore-lora-birefnet`); Qwen Text to image ohne LLM, MOSS UltraReal Pflicht (`fix/defaults-need-their-files`); LLM-Zeile unter dem Prompt, Name nur im Tooltip, LoRA-Haken bündig (`feat/llm-row-under-prompt`, im echten versteckten Fenster geprüft); Blindtest `tests/live_qwen_encoder.py` angelegt (`test/qwen-encoder-blind`).
- **Fill-Maske eingebaut** (Option A, Wahl des Users; `feat/fill-mask-crop-fade`): `bridge.soft_layer_mask` nutzt für Fill mit Qwen und Fibo `fillmask.crop_fade` (bis zum Ausschnittrand, an der Bildkante kein Auslaufen); Mask density startet bei 100 % statt 5 %. Tests `test_fill_mask_variants` (Regel 4 jetzt für crop_fade), `test_fill_outer_edge`, `test_mask_density` angepasst.
- **Fill-Masken-Testrunde** (`test/fill-mask-round`, `fix/fill-mask-rate-outline`; Anleitung `docs/tests/fill-mask-testrunde.md`): vier Varianten in `pccomfy/fillmask.py`; Stufe 1 `tests/test_fill_mask_variants.py` (144 Fälle je Variante, alle Regeln erfüllt, keine Variante läuft an einer Bildkante aus); Stufe 2 `tests/live_fill_mask.py` (40 Läufe, auf Wunsch des Users von 160 gekürzt, Messung, Blindbewertung mit 4 Kacheln), Bewertungsfenster am Bildschirm des Users geprüft. Gelaufen und vom User blind bewertet: Runde 1 (40), Runde 2 (16, nach seinen Notizen geändert) und Runde 3 (4); Ergebnis: „bis zum Ausschnittrand“ bei beiden Modellen am häufigsten gut, der schmale Rand von heute am seltensten.
- **Verlauf der letzten 20 Läufe** (Punkt 13, OpenFill T3b, `feat/run-history`; Entscheidungen des Users: Uhr-Symbol im Header, alles laden mit neuem Seed, LLM-Text mit Enhance aus). `pccomfy/history.py` speichert je fertigem Lauf alle Einstellungen (`_collect`) in `data/history.json`; Laden über `_apply_settings`, Prompt mit Strg+Z-Schritt. Test `tests/test_run_history.py`; mit echtem Tk (verstecktes Fenster) geprüft.
- Aufräumen der Planungsdokumente: PLAN.md nur noch offen + Entscheidungen, dieser Verlauf neu, Handoff als Technik-Anleitung, ideas.md nur offene Ideen, fertige Recherchen nach `docs/archiv/`. `photocraft-ai 0.15.1.bat` entfernt (Wunsch des Users). Alte, gemergte Branches und der Ordner `lanes/` gelöscht.

## 29.10.

- **Live-Vorschau** (Punkt 12, `feat/live-preview`): grobe Farben als Standard; jeder Lauf schickt `preview_method: taesd` mit (mit Datei scharf, ohne latent2rgb). TAESD-Dateien optional im Zahnrad (`taef2_decoder.pth` für Flux 2/3, Fibo, MOSS; `taeqi2_1_decoder.pth` für Qwen 2.1; `lighttaew2_1.safetensors` für Krea 2). Bereich nur während des Laufs über der Statuszeile, weg, sobald das Ergebnis in PhotoCraft liegt. Haken „Live preview“ am Ende der Advanced settings, bei jedem Start und nach Reset an. Keine Vorschau in der LLM-Phase und bei SeedVR2.
- **L3 Fenster-Politur** (Punkt 11): Doppelklick auf den Header (`feat/header-double-click`); Rechtsklick auf Modell-Chip mit Favorit und „Hide this model“ (`feat/model-chip-menu`; der Favorit kommt zuerst, vor dem zuletzt benutzten Modell; eine Funktion ohne sichtbares Modell wird grau); Haken „Shown in the plugin“ im Zahnrad (`feat/settings-show-models`); „Copy canvas“ im Header als PNG mit Transparenz und DIB (`feat/copy-canvas`, `Bridge.canvas_image`).
- **Header und Minimieren** (`feat/header-minimize`): Header vorerst leer (`f_logo` nimmt später das Bild des Users), Knopf „–“, eingeklappt nur der Header, Chevron zum Aufklappen.
- **Describe:** Wiederverwenden der Beschreibung, neuer Text erst beim zweiten Klick auf denselben Slot mit Zufalls-Seed (`feat/describe-reuse`); Beschreibung weiß an der Stelle der orangen Meldung mit Kopier-Symbol (`feat/description-spot`); Tag unter dem Slot in dunkler Box (`feat/slot-tag-box`).
- **Liste des Users 29.10. abends**, je Punkt ein Branch: PhotoCraft-Checkbox orange (`feat/photocraft-checkbox`), Slot-Bild in den Prompt ziehen (`feat/slot-drag-tag`), Slot-Symbole 19 px (`feat/slot-icons-smaller`), markierbare Beschreibung (`feat/selectable-description`), größere Zahlenfeld-Pfeile (`feat/bigger-spin-arrows`), Seed in den Advanced settings (`feat/seed-in-advanced`), Variants am Generate-Knopf (`feat/variants-on-generate`), Klick auf das Slot-Tag (`feat/slot-tag-click`), Hinweis mit `<image1>` (`feat/drag-hint-image1`).
- **Todos des Users 29.10.:** Prompt-Box hüpft nicht mehr (`fix/prompt-box-jump`), Upscale factor als Schalter (`feat/upscale-factor-switches`), kein Flackern mehr (`fix/fit-height-loop`), Auge für die Slot-Vorschau (`feat/slot-eye-preview`), Context in Prozent (`feat/context-percent`).
- **Design:** Refresh als ⟳, Reset als „Defaults“ (`feat/footer-refresh-icon`); dünner Scrollbalken am Prompt (`feat/prompt-thin-scrollbar`); Tipp mit Info-Symbol (`feat/tip-info-icon`); Prompt-Auswahl als Schalter (`feat/prompt-choice-switches`).
- **MOSS Text to image:** neue Startwerte (`feat/moss-t2i-defaults`); LoRA-Haken stellt Steps/CFG richtig um (`fix/lora-switch-steps`); Blindtest CFG (`docs/tests/moss-cfg.md`), Entscheidung CFG 3.0 / 35 Steps (`feat/moss-cfg3-35-steps`).
- **Seam-Korrektur je Modell** (`feat/seam-per-model`, `Model.seam`): Fibo immer, Flux nie, Qwen mit Haken.
- **Flux 3 Expand mit Outpaint-LoRA** (`feat/flux3-outpaint-lora`, `flux3-klein-outpaint.json`): A/B 64 Läufe, verschoben/gezoomt alt 10 von 32, neu 0 von 32; 10 s statt 24 s (`docs/tests/flux3-expand-lora.md`).
- **Krea 2 / MOSS Expand:** Describe-Knopf für die Umgebung (Commit bb18dbd, `Bridge.describe_scene`), A/B-Test (`docs/tests/krea-moss-expand-ab.md`), Seam-Testrunde mit 128 Bildern (`docs/tests/expand-seam-testrunde.md`); danach abgeschaltet und geparkt (`models.PARKED_EXPAND`). Der Commit liegt direkt auf `next`, weil eine parallele Sitzung den Branch gewechselt hatte.
- **Geparkte Workflows** erscheinen nicht mehr in der Workflow-Liste (`fix/hide-parked-workflows`).
- **Privates GitHub-Repo** und neues `README.md` (`docs/readme`).

## 28.10.

- **Ergebnis in PhotoCraft:** ohne Zwischenablage (`Bridge._place_png`, `layer.copyToDocument`), Varianten-Gruppe (`Bridge._group`), Feather-Vorschau als Quick Mask (`Bridge.show_feather`). Live bestätigt.
- **Fill Qwen/Fibo:** Layer mask „soft“ mit Rand außen (`imaging.outer_feather`), „auto“ entfernt, Context als Regler, neue Regler-Reihenfolge, „Image and mask“ ausgeblendet, vollständiger Reset (`tests/test_reset_all.py`), Fill-Tipp. Live bestätigt.
- **E2-Testrunde Context/Feather** (`docs/tests/e2-context-feather.md`): Fibo Fill Context 0.4; Remove nur ein Lauf; runde Ecken bei Rechteck-Auswahl.
- **Qwen Fill größer:** `FILL_PROMPT_LARGE` („Make it as large as the red rectangle …“). Live bestätigt.
- **Mask density** (Regler, Fill Qwen/Fibo 5 %, `layer.layerMask.edit`, PhotoCraft 0.17+).
- **Fill-Maske bis zum Ausschnittrand** (`imaging.crop_fade`): versucht und mit zwei Revert-Commits zurückgenommen (siehe PLAN, „Fill-Maske neu“).
- **Seam-Korrektur als A/B** (`feat/seam-correction`, `imaging.seam_correct`): Grundlage für die Entscheidung je Modell am 29.10.
- **Fibo Expand füllt den Rand** (`feat/fibo-expand-wording`, `docs/tests/fibo-expand-ab.md`: 30 von 30 statt 11 von 26). Expand-Maske an der Bildkante (`fix/expand-mask-canvas-edge`, `imaging.outpaint_mask`).
- **Kleinere Verbesserungen** (acht Branches `feat/fibo-sharpen-start` … `feat/hide-denoise`), Sharpen je Funktion (`feat/sharpen-per-function`), allgemeine Funktions-Tooltips (`feat/general-function-tips`, `models.FUNCTION_TIPS`), Fibo Refine mit Mix (`feat/fibo-refine-mix`), Zahlenfelder überarbeitet (`fix/number-fields`, `fix/number-box-unit`), Refine-Tipp „Add a short description …“ (`DESCRIBE_TIP`), Referenzbild-Vorschau (`feat/ref-preview`).
- **Edge feather beim Start** mit dem Wert der Funktion (`fix/feather-start-value`). Live bestätigt.
- **Start ohne .bat:** Desktop-Verknüpfung (`feat/desktop-shortcut`, `photocraft-ai.pyw`, `python -m pccomfy shortcut --photocraft <exe>`). Autostart-Code für später (`autostart.py`, `python -m pccomfy autostart install|uninstall|status`; liest `PHOTOCRAFT_CONTROL_PORT` usw. aus Umgebungsvariablen, Wächter im Run-Schlüssel, ein Start je PhotoCraft-Sitzung); nicht eingerichtet. Für die Auslieferung nur als Schalter im Zahnrad („Start with PhotoCraft“, aus), Hinweise zu Virenscannern und Installer im Archiv-PLAN, E4.
- **Ranking im Tooltip** (`models.RANKING`, `models.function_tip`).

## 27.10.

- **Liste A** (Abstände, Chevron, „Custom LoRAs:“, ComfyUI-Punkt grün/rot, Slider rechts in einer Spalte und eintippbar (`ValueBox`), „Advanced settings“) und Nachrunde: Ergebnis über einer Korrekturebene, Flux 2 Refine startet auf „Default“, Qwen ohne Turbo, Expand/Edit getauscht, kürzere Texte.
- **Feste Startposition** (`win_pos`, `winlink.first_position`). Live bestätigt.
- **Flux 2 Klein:** obsxrver-Datei `flux-2-klein-9b_int8_convrot.safetensors` (A/B gleichwertig, `tests/live_flux2_file_compare.py`); alle 24 Dateien mit Download-Link (`docs/model-downloads.md`).
- **Zahnrad-Fenster:** „Choose another file…“ mit Relink, Undo, Reset to startup; Tabs „Models“ und „Credits“.
- **Fensterkopf „Funktion zuerst“** (Studie in `docs/archiv/ux-funktion-zuerst.md`), Funktions-Symbole (`fn-<key>` in `icons.py`), Schrift Inter (Recherche in `docs/archiv/ui-schriften.md`). Live bestätigt.
- **PhotoCraft-Befehle geprüft** (`docs/photocraft-befehle.md`).

## 26.10. und davor

- **Phase 0:** Aufteilung von `gui.py` in Mixins, `clipboard.py`, Test-Runner.
- **L1:** Modell-Erkennung, Zahnrad-Fenster, Preflight, graue Tabs (`docs/archiv/entscheidungen-L1.md`).
- **L2:** Multi Image Edit mit Slots, Drag and Drop, Strg+V, Ausschneiden mit BiRefNet, Beschreiben mit Qwen 3.5 9B (`docs/archiv/entscheidungen-L2.md`, `docs/prompting-multi-image.md`).
- **UI-Runde 26./27.10.:** Icons (Lucide-Stil, ISC), PhotoCraft-Slider, Undo/Redo-Knöpfe, Papierkorb am Prompt, Knopfzeile über dem Prompt, nur ein leerer Slot, Downloadlinks, Starter `photocraft-ai neuer-nutzer.bat`.
- **OpenFill-Recherche** (`ideas.md`).
