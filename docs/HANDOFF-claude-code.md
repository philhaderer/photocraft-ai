# Handoff: PhotoCraft x ComfyUI Plugin (Stand 2026-10-27)

Zweck: Alles, was die nächste Claude-Code-Sitzung wissen muss, um direkt weiterzuarbeiten. Lies zusätzlich `CLAUDE.md` (Arbeitsweise, Regeln) und `PLAN.md` (**Abschnitt 3 = die Arbeitsliste in ihrer Reihenfolge**; OpenFill-Ideen im Detail in `ideas.md`). Abschnitt 6 hier hält die Befunde und Optionen zu den Punkten der Liste vom 27.10.

## 1. Rolle und Regeln des Nutzers (immer)
- Rolle: App-Programmierer, UI-Designer und ComfyUI-Experte. Der Nutzer schreibt Deutsch; erklärt wird in einfachem Deutsch, ohne Git-Jargon.
- Schreibt er **Englisch** (auch nur eine Zeile): zuerst seine Nachricht in korrektem Englisch zurückgeben („Corrected version of your message:“ + Zitat), dann antworten.
- **An Entscheidungspunkten die Optionen nennen** (Empfehlung zuerst), nie still wählen. Bei Wortlaut/Tooltips/Design im Zweifel fragen.
- Nebenwirkungen (Downloads, Neustarts, Löschungen, GPU-Läufe, Installationen) nur mit Erlaubnis. ComfyUI und Plugin startet er selbst neu.
- **Git nach Standard und nachvollziehbar** (Details `CLAUDE.md`): je Änderung ein Branch aus `next` (`feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`), **vor der ersten Änderung anlegen**, nie direkt auf `next`; Tests grün, dann `git merge --no-ff` in `next`; nie pushen, nie Verlauf umschreiben. Conventional Commits (`typ: Zusammenfassung`, Body mit Was und Warum), Trailer mit dem Modell der laufenden Sitzung. Nach jedem Git-Schritt auf Deutsch sagen, was passiert ist. **Vor jedem Löschen eines Branches fragen.**
- In PowerShell mehrzeilige Commit-Nachrichten mit `git commit -F <datei>` (Datei im Scratchpad).
- Keine README-Politur. `README.pl.md` ist Upstream und bleibt. `photocraft-ai 0.15.1.bat` ist sein Starter: nie löschen.
- Checkpoint-Graph und Fooocus-Code bleiben vorerst. Keine automatische Prompt-Ergänzung bei „remove …“ (nur Tipp unter dem Prompt).
- Sein Bildton: Fenster 380 px fest breit, Titelleiste `#404040`; Flächen `#282828` (`PANEL`), Fenstergrau `#535353` (`BG`), Akzent Orange `#f28c28`; PhotoCrafts Slider-Spur (dunkler Teil) `#686868`.
- „Perfekt“ (nicht ohne Nachfrage anfassen): Qwen 2.1 Edit/Fill/Expand/Remove; Flux 2 und Flux 3 Edit; Flux 3 Upscale; Flux 3 Text to image; MOSS Text to image und Expand; Fibo Edit whole image; Fensterkopf und Schärfe des Fensters.
- Rechtzeitig sagen, wenn ein Chat zu lang wird (`PLAN.md`, Abschnitt 6).

## 2. Repo und Git-Stand
- Pfad `C:\programs\photocraft-comfyui-bridge`, Fork von Peszemeszek/photocraft-comfyui-bridge. Nur lokal, nichts gepusht.
- Branches: `main` (Upstream), `windows-fibo` (abgenommener Stand 6aff33a), `refactor/split-gui` (Phase 0, in `next`), **`next` = Integrationsstand, den der Nutzer testet**.
- Arbeits-Branches vom 26./27.10., alle in `next` gemergt und **noch nicht gelöscht** (Löschen nur nach Rückfrage): `feat/prompt-clear-and-t2i-tip`, `feat/generate-row-above-prompt`, `fix/one-empty-slot`, `fix/add-file-dialog-parent`, `feat/drop-replaces-slot`, `feat/window-icons`, `feat/photocraft-sliders`, `feat/model-download-links`, `docs/handoff-2026-10-27`, `docs/handoff-decisions`; dazu aus der zweiten Sitzung 27.10.: `fix/layout-spacing`, `feat/footer-status`, `feat/slider-column`, `feat/advanced-settings`, `docs/list-a-done`, `fix/paste-above-adjustment-layer`, `feat/small-tweaks-2`, `fix/lora-row-gap`, `feat/refine-default-prompt`, `chore/shorter-lora-labels`, `docs/plan-cleanup`, `feat/start-position`, `test/flux2-file-compare`, `feat/flux2-obsxrver-file`, `feat/choose-another-file`, `feat/settings-relink-tabs`, `docs/ux-function-first`, `fix/settings-wording-undo`, `feat/function-first`, `docs/handoff-function-icons`; dritte Sitzung: `feat/function-icons`, `docs/function-icons-done`, `fix/function-icon-gap`, `docs/ui-fonts`, `feat/inter-font`, `docs/inter-font`.
- Ungetrackt im Repo-Ordner: `photocraft-ai 0.16.bat` (Starter des Nutzers für PhotoCraft 0.16): nicht anfassen, vor dem Einchecken fragen.
- Tags: `backup-2026-10-26` (6df02df, vor Phase 0), `vor-claude-code` (65e955f).
- Lane-Klone `lanes/L1`, `lanes/L2` sind Altlast (per `.git/info/exclude` ignoriert). Archiv: `docs/archiv-lanes/`.
- Tests: `python tests/run_all.py` (41 Dateien, alle grün, ca. 16 s). Python des Nutzers: Pfad in `data/python.txt`.
- Diagnose: `data/exchange/last-graph.json`, `data/exchange/runs.jsonl`; ComfyUI-Historie über `http://127.0.0.1:8188/history`.

## 3. Umgebung
- ComfyUI: `C:\programs\ComfyUI-Easy-Install Cuda13\ComfyUI` (0.42.0), Modelle in `C:\AI_Models` (diffusion_models, clip, vae) und `D:\AI_Models\Lora`. RTX 4070 Ti Super (16 GB), 64 GB RAM. Release 1 nur 16 GB.
- PhotoCraft 0.15.1 portable unter `C:\programs\photocraft-0.15.1-windows-x64-portable`. Der Nutzer hat einen Starter `photocraft-ai 0.16.bat` (zeigt auf `photocraft-0.16.0-windows-x64-portable`) in den Repo-Ordner gelegt, ungetrackt: nicht anfassen, vor dem Einchecken fragen.
- **Echtes Fenster prüfen ohne PhotoCraft** (nur, wenn der Nutzer es nicht selbst prüfen kann; Screenshots dauern ihm zu lange): ein Skript im Scratchpad setzt `PCCOMFY_HOME` auf einen Temp-Ordner, `gui.winlink.available = lambda: False`, baut `gui.App(cfgmod.load())`, wählt Tab/Modus und macht nach **8 s** (`root.after(8000, …)`, sonst läuft das Start-Refresh noch und setzt das Modell zurück) mit `PIL.ImageGrab` einen Screenshot des Fensters. Rote Meldung „Can't connect to PhotoCraft“ ist dabei normal.
- Python des Nutzers hat veraltete Zertifikate für Civitai (SSL-Fehler): Civitai-API per PowerShell `Invoke-RestMethod` abfragen; Hugging Face geht auch aus Python.

## 4. Was gebaut und in `next` ist
**Phase 0, L1, L2** wie im Plan. Details: `docs/entscheidungen-L1.md`, `docs/entscheidungen-L2.md`, `docs/prompt-aufbau.md`, `docs/prompting-multi-image.md`.

**Sitzung 26.10. abends** (Kurzfassung): Conventional Commits, Tests unter Windows, `undo.png`, „Max. images“ in der Slot-Kopfzeile, Beschreiben schreibt sichtbar ins Prompt-Feld, Slot-Icons als Vektoren (`pccomfy/icons.py`, Lucide-Stil, ISC: **in den Release-Credits nennen**), Starter `photocraft-ai neuer-nutzer.bat`, Expand für Flux 3 und Krea 2 wieder an, dünner Scrollbalken, Masken-Analyse (Option A offen).

**Sitzung 26./27.10. (diese):**
- **Papierkorb** rechts neben „Prompt“: leert das Feld, Strg+Z im Feld holt den Text zurück (`_clear_prompt`, gui_prompt.py); flach, ohne Kasten.
- **Tipp bei Text to image** (alle Modelle): „Text to image: a completely new image is added to the canvas as a new layer.“ (`models.T2I_TIP`, vom Nutzer abgenommen).
- **Knopfzeile Generate/Cancel/Undo/Redo** steht jetzt über „Prompt“ (unter den Funktionen); Fortschrittsbalken und Status bleiben unten.
- **Slots:** nur gefüllte Slots plus genau ein leerer (`_refs_visible`); „Add file“-Dialog mit `parent` und pausiertem Winlink-Watchdog (`App._dialog`); Drop auf ein gefülltes Slot-Bild ersetzt es (erstes Bild ersetzt, Rest wird angehängt; `RefSlots.put`, `add_files(at=)`).
- **Icons** (20 px, `ThemeMixin._icon`, ICON_PX in gui_theme.py; Slot-Icons bleiben 24 px): Plus, Zahnrad, Undo/Redo, Chevrons (Negative prompt, Advanced, LoRA-Zeile), X, Kopieren, Speichern, Papierkorb; unter der Maus orange, gesperrt grau. Spinbox-Pfeile als schmale Chevrons (14 px, eigenes ttk-Element, `_spin_arrows`). Vorschaublatt: `data/icon-preview.png`.
- **Slider im PhotoCraft-Look:** neues Widget `Slider` (gui_common.py, Canvas: dünne Spur, links hell `#e6e6e6`, rechts dunkel `#2a2a2a` → **muss `#686868` werden**, weißer Knopf mit Pillow geglättet); Wert rechts in einem Kästchen (`Value.TLabel`, Breite `VALUE_W = 9`). `_scale_clicks` und der TScale-Stil sind weg.
- **Downloadlinks:** `manifest.py` hat für alle 24 Dateien direkte Links (Flux 2 Klein seit 27.10. über obsxrver) (HF `resolve/main`, Civitai-Download-API), Größe (`File.size`, `size_text`) und Lizenz-/Gated-Hinweis; geprüft per Größe und (wo nötig) SHA256 gegen die Kopien des Nutzers, jeder Link per HEAD. Tabelle: `docs/model-downloads.md`. Das Zahnrad-Fenster zeigt die Größe neben „download“.

**Zweite Sitzung 27.10.:**
- Liste A komplett (Abschnitt 6.A). Slider-Spur jetzt `#686868`; alle Slider `SLIDER_W` = 140 px rechts mit `ValueBox` (eintippbar, nur Ziffern und ein Komma/Punkt, Klick markiert alles).
- **Korrekturebene oben:** Vor jedem Einfügen legt `_pixel_target` (bridge.py) eine leere Ebene `pccomfy-target-<tag>` an, das Ergebnis kommt darüber, die Hilfsebene wird gelöscht (vorher landete es in der Maske der Korrekturebene). Vom Nutzer live bestätigt.
- **Startposition:** Position wird gespeichert (`win_pos` im State) und beim Start gesetzt, wenn sie auf einem Monitor liegt; sonst beim ersten Link rechts oben in PhotoCraft unter der Menüleiste (`winlink.first_position`, `below_menu_bar`). Der Menü-Wächter ignoriert Klicks auf das Plugin-Fenster selbst (Ursache des „Verschwindens“ beim Ziehen). Live noch nicht bestätigt.
- **Flux 2 Klein:** Workflows und Manifest nutzen die obsxrver-Datei `flux-2-klein-9b_int8_convrot.safetensors` (A/B-Test gleichwertig, Skript `tests/live_flux2_file_compare.py`). Alle 24 Dateien haben jetzt einen Download-Link.
- **Zahnrad-Fenster:** Tabs „Models“ und „Credits“ (weitere Settings-Tabs später möglich); keine eigene Statuszeile mehr (Punkt und Refresh sind im Plugin). Neben jeder Datei „Choose another file…“; unten Expected / Current / New file, gespeichert wird erst mit „Relink“ (die erwartete Datei selbst wählen = Link entfernen). „Undo“ nimmt nur Relinks zurück, „Reset to startup“ stellt den Stand beim Start her und leert die Undo-Liste. Verknüpfte Datei: „(your file: …)“.
- **Fensterkopf „Funktion zuerst“:** oben 8 Funktions-Buttons (`Tab.Toolbutton`, 2 Spalten, Symbol links: Platzhalter `placeholder` bzw. PNG aus `pccomfy/assets/functions/`), darunter die 6 Modelle als Umriss-Chips (`Chip.Toolbutton`, 3 Spalten; unpassend = grau, Dateien fehlen = rot `Missing.Chip.Toolbutton`). Funktion wechseln wählt bei Bedarf ein Modell: das zuletzt dafür benutzte (`model_by_mode` im State), sonst das erste passende in fester Reihenfolge. Funktionen sind nie grau. Variablennamen blieben: `rb_modes` = Funktionen, `rb_tabs` = Modell-Chips.
- **Flux 2 Refine** setzt beim Wählen immer „Default“ (ein Undo-Schritt im Feld). **Qwen:** Turbo in allen Funktionen anfangs aus. **Funktionen:** „Expand image“ und „Edit whole image“ getauscht (`MODE_LABELS`). Leere Zeile nach dem letzten Custom LoRA weg. Texte: „Mix Source/New Image“, „DMD2 LoRA (8 steps)“, „UltraReal LoRA“.

## 5. Entscheidungen des Nutzers (komplett)
- Release 1 nur 16 GB, 8-GB-Empfehlungen nur Doku. Fast Mode gestrichen.
- Krea 2 Expand und Flux 3 Expand: zum Testen an. Flux 3 Expand funktioniert; Krea 2 Expand nur einseitig brauchbar (alt 6.10). Endgültige Entscheidung steht aus.
- Qwen-Slotzahl: 8 bleibt.
- Veröffentlichung: neues Repo ohne Upstream-Verlauf, Credits Pflicht, erst kurz vor dem Release; bis dahin `windows-fibo`.
- Reihenfolge: **kleine Verbesserungen zuerst** (PLAN.md 8.A), dann weiter nach Plan; Easy Mode zuletzt. Easy-Mode-Ranking Fill: Qwen, Fibo; Expand: MOSS, Flux 2, Fibo, Qwen.
- Rechtsklick auf Modell-Tab: Favorit, Tab ausblenden, Workflow-JSON speichern. Minimize = Einklappen (hide/show).
- Krea-Styles bis 50 per Bildauswahl; Tutorial-PSDs mit Testbild; Tooltips bei jedem Start.
- Tipp-Wortlaut Text to image: abgenommen. Icons: 20 px (Slot-Icons 24 px). Drop auf mehrere Bilder: erstes ersetzt, Rest anhängen.
- Strg+Z/Strg+Y: bleibt wie heute, keine Plugin-Tastenkürzel (27.10.). ComfyUI-Punkt: rot = nicht verbunden, grün = verbunden (27.10.).
- 27.10. (zweite Sitzung): „PhotoCraft“ unten weg; Slider 140 px, Werte immer eintippbar, nur Ziffern; Qwen ohne Turbo; Expand/Edit getauscht; Flux 2 Refine startet auf „Default“; Screenshots nur, wenn der Nutzer etwas nicht selbst prüfen kann.
- Branches: vor jedem Löschen fragen.

## 6. Aufgaben für den nächsten Chat (Liste des Nutzers vom 27.10., auch in PLAN.md 8)
Jede Aufgabe auf eigenem Branch, Optionen vorher nennen, wo Design oder Wortlaut zu wählen ist. **Reihenfolge: A zuerst, dann B, C, D, dann E.**

### A. Kleine Verbesserungen: **erledigt 27.10. (zweite Sitzung), in `next`**
Entscheidungen des Nutzers dazu: „PhotoCraft“ unten ganz weg; ComfyUI = Text + farbiger Punkt (grün/rot, grau bis zum ersten Refresh), im Zahnrad-Fenster gleich (`conn_status`/`set_dot`, gui_common.py); Sliderbreite 140 px (`SLIDER_W`); Wert-Kästchen immer editierbar (`ValueBox`, gui_common.py: Enter/Fokusverlust übernimmt, %, Komma und „hard edge“ verstanden, auf den Bereich begrenzt, mit dem Slider grau); Textzeile über dem Balken nur, wenn sie Text hat (`_show_pl_line`). Link-Buttons `width=0` (clam zentrierte „Advanced“). Sharpen/Match/Feather/Layer mask liegen in `f_post` oben in „Advanced settings“. Offen: lange Texte links neben einem Slider werden gekürzt („DMD2 speed LoRA (8 ste…“, „Mix source image/new imag…“); Wortlaut kürzen oder so lassen, Nutzer fragen. Live-Test (echtes Fenster mit PhotoCraft, 150 %, Werte tippen) offen.

Ursprüngliche Aufgaben:
1. **Leerzeile unter den Drop-Slots** (vor dem Befüllen) weg. Vermutung des Nutzers: Platz für den Bild-Tag. Befund im Code: im leeren Slot packt `_refs_redraw` (refslots.py) ein leeres `ttk.Label(cell, text="")` als Platzhalter unter die Box; dazu kommt `lbl_refnames` („Add a picture, then name it in your text.“). Den leeren Platzhalter entfernen; prüfen, dass die Zeilen beim Befüllen nicht springen.
2. **Leerzeile nach „Advanced“** weg (gui.py: `f_adv`/`adv_body`, Abstände `pady`; im Screenshot vom 27.10. sichtbar unter dem geschlossenen „Advanced“).
3. **Chevron bei „Advanced“ zu weit rechts:** Link.TButton mit `compound="left"` zentriert Bild+Text bzw. hat Innenabstand; links bündig machen (`anchor="w"`/Padding 0) wie bei „Negative prompt“, beide gleich.
4. **„Extra LoRAs (style, detail ...)“ → „Custom LoRAs:“**, „+ Add“ ganz nach rechts (`pack(side="right")`), Leerzeile danach weg (gui.py, `f_xl`/`head`).
5. **Text „PhotoCraft“ unten links weg.** Was er heute bringt: `v_conn` zeigt „PhotoCraft ●/○“ = ob der PhotoCraft-Steuerport (127.0.0.1:7878) erreichbar ist (gui_state.py `refresh`). Ohne ihn fehlt diese Anzeige; da das Plugin ohne PhotoCraft nicht arbeiten kann und Fehler ohnehin als Meldung kommen, ist er verzichtbar. Mit dem Nutzer bestätigen, dann entfernen (und Tests anpassen).
6. **ComfyUI-Punkt:** rot, wenn nicht verbunden, grün, wenn verbunden (vom Nutzer am 27.10. bestätigt). Heute nur Zeichen ●/○ im Text; farbiger Punkt braucht ein eigenes Label/Canvas (`DONE_GREEN`/`ERROR` aus gui_common). Das Zahnrad-Fenster zeigt den Punkt ebenfalls (ui_settings.py Zeile ~454): dort einheitlich.
7. **Slider-Farbe:** dunkler Teil der Spur `#686868` (PhotoCraft) statt `#2a2a2a` (`Slider.REST`). Hellen Teil und Knopf mit PhotoCraft vergleichen lassen.
8. **Slider überall rechts, gleich breit, fest:** alle Slider in einer rechten Spalte mit fester Breite; auch die Workflow-LoRA (heute unter dem Haken „LoRA“, gui.py `f_lora` in Zeile 2) und die Stage-LoRAs (heute `length=110`) rechts neben ihrem Text. Gemeinsame Breite als Konstante (z. B. in gui_theme.py), Wert-Kästchen gleich breit.
9. **Werte eintippbar:** das Wert-Kästchen wird ein Eingabefeld (ttk.Entry im Kästchen-Stil); Enter/Fokusverlust übernimmt, Werte werden auf den Bereich begrenzt; Anzeige-Format wie heute (%, 0.00, „hard edge“ = 0). Feather nimmt 0 an und zeigt „hard edge“. Option zuerst mit dem Nutzer klären: Feld immer editierbar (empfohlen) oder erst per Doppelklick.
10. **Unter „Advanced“ verschieben:** „Sharpen result“, „Match colours“, „Edge feather“ und das Dropdown „Layer mask“; „Advanced“ heißt neu **„Advanced settings“**. Achtung: Feather und Layer mask werden heute je Modus ein-/ausgeblendet (`_update_feather_state`, gui_modes.py; `f_lm`, `_sharp_widgets`, `_match_widgets`): die Logik muss im neuen Eltern-Frame (`adv_body`) weiter stimmen. Tests in `test_feather_state.py`, `test_round5.py` prüfen das.

### B. Wichtig
11. **Feste Startposition:** Nach dem PhotoCraft-Start wird das Plugin oft zu weit links oben gesetzt; Drag and Drop nach unten lässt das Fenster dann kurz verschwinden. Es soll an einer festen Position starten. Zuerst nachstellen (mit PhotoCraft, nur mit dem Nutzer). Ansatz: Position beim Start selbst setzen (`root.geometry("+x+y")`, z. B. rechts im PhotoCraft-Fenster oder gespeicherte letzte Position, auf den Bildschirm begrenzt), bevor `winlink.link` das Fenster an PhotoCraft hängt. Prüfen, ob Winlink/`_fit_height` die Position verschiebt. Optionen nennen (feste Ecke vs. letzte Position).
12. **Flux 2 Klein 9B: erledigt 27.10.** A/B-Test (`tests/live_flux2_file_compare.py`, Ergebnis in `data/compare-flux2/20261027-094157/`): obsxrver-Datei gleichwertig (PSNR 27 bis 41 dB, gleiche Komposition, gleiches Tempo, 3,6 s je Bild). Entscheidung des Nutzers: Option B, Workflows (`flux2-klein-*.json`), `models.py` und `manifest.py` nutzen jetzt `flux-2-klein-9b_int8_convrot.safetensors` mit Link `obsxrver/…/resolve/main/diffusion_models/…` (auf `main` im Unterordner, gleiche SHA256 bd041cec…). Die alte Datei `flux-2-klein-9b-int8-ConvRot-comfyui.safetensors` liegt beim Nutzer noch; er bindet sie über C.13 ein, wenn er will. Früherer Befund: Sakujo-Repo nicht mehr öffentlich (401). Die vom Nutzer genannte Datei `obsxrver/ComfyUI-Native-INT8_ConvRot` → `flux-2-klein-base-9b-int8-ConvRot.safetensors` (Commit 1ddfc10) wurde am 27.10. per Range-Read verglichen: **nicht bytegleich** (9 405 841 414 statt 9 405 846 682 Byte, SHA256 66462911… statt ff4d4314…; gleiche 429 Tensoren, aber 114 Quantisierungs-Einträge und die Gewichtsdaten unterscheiden sich; „base“ = wohl das nicht destillierte Base-Modell). **Umbenennen geht nicht.** Am 27.10. (zweite Sitzung) auch die Datei ohne „base“ verglichen (`obsxrver/…/flux-2-klein-9b_int8_convrot.safetensors`, Commit d225df1, nur der Kopf per Range-Read): **nicht bytegleich**: 9 439 894 544 Byte, SHA256 bd041cec…; 425 statt 429 Tensoren, Namen ohne `model.diffusion_model.`-Präfix (BFL-Schema), 112 statt 114 int8-Schichten, Quantisierungs-Metadaten im Kopf. Eine andere Umwandlung; ob sie mit unserem Workflow gleich gut läuft, ist ungetestet. Der Nutzer hatte am 27.10. morgens einen Download davon im Browser begonnen (`C:\AI_Models\diffusion_models\…wc7mKQKj.safetensors.part` plus eine 0-Byte-Datei gleichen Namens). Optionen für den Nutzer: A Link leer lassen (heute), B die destillierte Fassung eines anderen Uploaders testen (`obsxrver/…/flux-2-klein-9b_int8_convrot.safetensors`, `Winnougan/…`, `wraps/…`, je ca. 9,4 GB, Download nur mit Erlaubnis), C eigene Fassung beim Release anders bereitstellen (Lizenz: FLUX non-commercial beachten).

### C. Neue Funktionen
13. **Eigene Datei statt Modell (Settings):** neben jeder Modell-Datei im Zahnrad-Fenster ein Knopf, mit dem der User eine eigene Datei wählt, die statt der erwarteten benutzt wird. Wortlaut vorschlagen, Nutzer wählt; Vorschläge: „Use my own file…“ (empfohlen), „Replace with my file…“, „Choose another file…“. Technik: die Zuordnung (erwarteter Name → eigener Name aus ComfyUIs Liste) in config speichern; `fix_lora_names`/Graph-Anpassung (workflows.py) setzt beim Senden den eigenen Namen ein; Erkennung (inventory.py) zählt die Datei als vorhanden. Auswahl aus ComfyUIs Dateiliste des passenden Ordners (nicht freier Dateidialog, ComfyUI kennt nur seine Ordner).
14. ~~Strg+Z / Strg+Y~~: **gestrichen** (Entscheidung 27.10.: „das lassen wir so“). Strg+Z/Strg+Y bleiben wie heute (Text-Undo im Prompt-Feld); keine Plugin-Undo-Tastenkürzel bauen.

### D. Recherche und Entscheidungen (nichts bauen, Ergebnis vorlegen)
15. **Funktionen zuerst, Modell darunter?** Der Nutzer überlegt, die Funktionen (Text to image, Edit, Fill …) als erste Wahl oben zu setzen und das Modell darunter, weil Nutzer eher ihre Aufgabe wählen. Folgen für die UX aufschreiben: was passiert mit gesperrten Kombinationen (heute: Funktion grau je Modell → künftig Modell grau je Funktion), Start-/Leerzustände (`start_state`, ui_settings.py), Easy-Mode-Ranking (wählt dann automatisch das beste Modell je Funktion: passt gut zusammen), Rechtsklick-Favoriten, Presets/gespeicherter Zustand, Platzbedarf bei 380 px, Tooltips je Modell. Optionen nennen (z. B. A Funktion oben + Modell-Dropdown, B Funktion oben + Modell-Tabs, C bleibt), Empfehlung.
16. **UI-Fonts:** state of the art recherchieren und drei vorschlagen (z. B. Inter, Segoe UI Variable, IBM Plex Sans / Geist / Noto Sans prüfen): Lizenz (mitlieferbar?), auf Windows vorhanden oder einzubetten, wie Tk eine mitgelieferte Schrift lädt (Tk kann keine Font-Datei direkt laden: `AddFontResourceEx` per ctypes vor dem Start), Lesbarkeit bei 9/10 pt und 150 %. Heute: `FONT = "Segoe UI"` (gui_common.py).

### E. Danach laut Plan (offen aus der alten Liste)
- **Refresh/Reset** kleiner und klarer (alt 6.7): A ⟳-Icon neben den Status-Punkten + „Defaults“ als Text-Knopf (empfohlen), B Menü „⋯“, C zwei Icons, D Reset ins Zahnrad. Hängt mit A.5/A.6 zusammen (Fußzeile).
- **Krea 2 Expand** mehrseitig (alt 6.10): A nur einseitig, mehrseitig in Runden (empfohlen), B abschalten, C nur Tooltip.
- **Flux 3 Expand:** Steps prüfen (`runs.jsonl`, `last-graph.json`) und Startwert in `models.py` setzen; Entscheidung, ob es an bleibt (alt 6.11).
- **Masken-Option A** und **Seam-Korrektur T2** warten auf Freigabe (alt 6.12).
- Restliche Design-Vorschläge (alt 6.3): Prompt-Feld mit `ThinScrollbar`, runde Radios und echte Checkbox im PhotoCraft-Look, gesperrte Felder ausblenden oder einheitlich grau, „Image and mask“ ohne Rahmen, Tipp-Text gedämpft mit Info-Icon (Icon liegt im Vorschaublatt), Fortschrittsbalken nach „Done“ neutral, Raster 4/8 px. Teilweise überholt durch A.10.

## 7. Befunde zum Weitergeben
- **Gleicher Seed, anderes Bild (Flux 2):** Edit schickt das sichtbare Dokument; nach Lauf 1 lag dessen Ergebnis obenauf. Gegenprobe: Generieren, Undo, gleicher Seed noch einmal.
- **Branches löschen** ändert nichts am Code: Ein Branch ist nur ein Namensschild; nach dem Merge steckt alles in `next`.
- **flux2-vae:** die Kopie in `Comfy-Org/Flux-2-Dev` ist bytegleich mit der des Nutzers; die in den Klein/MOSS/Fibo-Repos sind 2264 Byte kleiner (anderer Dateikopf) und laden genauso.
- **Lizenzen für den Release:** Fibo 2.0 (CC BY-NC) und die FLUX.2-Dateien nur nicht-kommerziell; Lenovo UltraReal (Civitai) verlangt Nennung von Danrisi; Lucide-Icons (ISC) nennen; Inter (SIL OFL 1.1, `pccomfy/assets/fonts/OFL-Inter.txt`).

## 8. Live-Tests, die noch offen sind
- **Aus der dritten Sitzung 27.10.:** Funktions-Symbole bei 100 % und 150 %, normal, gewählt (orange), grau; Symbol und Text linksbündig, 8 px dazwischen. Schrift Inter (`pccomfy/fonts.py`, `font()` in gui_common.py, eine Stufe kleiner; Vergleich mit `PCCOMFY_NO_INTER=1`): Schärfe, gekürzte Texte, Fensterhöhe, Zahnrad-Fenster, Tooltips, Menüs.
- **Aus der zweiten Sitzung 27.10., Ende:** Funktion wechseln wählt das richtige Modell, rote/graue Chips; Zahnrad: Choose another file → Relink, Undo, Reset to startup, Tabs (laut User „noch genauer zu testen“). Bestätigt: neuer Fensterkopf (Chips, Namen, Höhe, 150 %), Startposition, Flux-2-Lauf mit der obsxrver-Datei.
- **Aus der zweiten Sitzung 27.10.:** Wert-Kästchen tippen (Enter, Wegklicken, nur Ziffern), Slider-Spalte bei 150 %, „Advanced settings“ mit Sharpen/Feather/Layer mask je Funktion, ComfyUI-Punkt grün/rot (ComfyUI beenden), Flux 2 Refine → „Default“ und Strg+Z, LoRA löschen ohne Leerzeile, Qwen ohne Turbo (Laufzeit, Qualität).
- **Aus der ersten Sitzung 26./27.10.:** Papierkorb + Strg+Z; Knopfzeile über dem Prompt; nur ein leerer Slot; „Add file“ mit PhotoCraft daneben (kein Doppelbild mehr?); Bild auf ein gefülltes Slot-Bild ziehen (auch mehrere); Icons unter der Maus orange, gesperrt grau; Spinbox-Chevrons klickbar; Slider ziehen/klicken, gesperrt grau; alles bei 150 %.
- Neuer Nutzer: `photocraft-ai neuer-nutzer.bat`, Varianten 1 bis 4.
- Flux 2 Text-to-Image mit und ohne Enhancer.
- Scrollbalken im echten Betrieb (Advanced offen, Qwen mit vielen Slots, 150 %).
- Beschreiben: erste Zeile, Ersetzen, von Hand geänderte Zeile bleibt.
- Flux-3- und Krea-2-Expand nach den Änderungen aus E.
Bestätigt: Slot-Icons, Tags beim Modellwechsel, Qwen 2/4/8, Zahnrad/Fußzeile bei 380 px, Tab-Farben, Einstellungsfenster beim Schließen von PhotoCraft, 150 % Skalierung, Tipp-Text, zentrierter Tag, Flux-2-Scheduler-Auswahl, Tipp-Wortlaut Text to image.

## 9. Danach (Plan)
Die Reihenfolge steht nur noch in `PLAN.md`, Abschnitt 3 (dort sind auch die OpenFill-Ideen aus `ideas.md` eingeplant). Punkt 0 (Funktions-Symbole) und D.16 (Schrift Inter) sind gebaut. Als Nächstes: D.6 (PhotoCraft-Befehle), E, L3 (Rechtsklick-Menü jetzt auf den Modell-Chips).
