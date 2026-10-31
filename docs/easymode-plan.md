# Easy Mode: Plan mit Optionen (PLAN.md Punkt 17)

Stand 2026-10-31. Nur ein Plan, noch kein Code. Grundlage: `PLAN.md` (Abschnitt 2, Punkt 17), `pccomfy/models.py`, `pccomfy/manifest.py`, `pccomfy/inventory.py`, `pccomfy/gui.py`, `gui_modes.py`, `gui_common.py`, `gui_state.py`, `ui_settings.py`, `config.py`, `docs/archiv/ux-funktion-zuerst.md`, `docs/erledigt.md`. Die Größen in Abschnitt 2 wurden mit einem Skript direkt aus `manifest.FILES` und `inventory.mode_files` berechnet (das ist dieselbe Regel, nach der das Plugin ein Modell anbietet). Jede Entscheidung hat Optionen und eine **Empfehlung**; nichts ist schon festgelegt.

Die Idee: Ein einziger Schalter reduziert das Fenster auf das Nötigste für Einsteiger: Funktion wählen, Prompt, Generate, Undo. Das Modell und alle Regler wählt das Plugin.

---

## 0. Was es heute schon gibt (geprüft im Code)

- `models.RANKING` hat nur `inpaint` (Fibo, Qwen), `remove` (Fibo, Qwen) und `outpaint` (Flux 2, Flux 3, Qwen, Fibo). Für Text to image, Edit, Multi Image Edit, Upscale und Refine gibt es **kein Ranking**. Der Kommentar dort sagt schon: „Also the order for Easy Mode“.
- `ModeMixin._model_for_mode` (gui_modes.py, Zeile 186) wählt heute: Favorit, dann zuletzt benutztes Modell, dann die feste Reihenfolge `models.MODELS`. Das Ranking nutzt es **nicht**. Der Docstring sagt: „Easy Mode will choose the best one later“.
- `config.py` hat schon den Kommentar „the right-click menu (lane L3) and Easy Mode read and write them only through these“ über `favorites()` / `hidden_tabs()`.
- `inventory.Inventory.tab_status` sperrt ein Modell ganz, wenn **einer** seiner Funktionen eine Datei der Standardeinstellungen fehlt. `SettingsMixin._model_usable` fragt genau das ab.
- `SettingsMixin.start_state()` kennt drei Zustände: `""` (Modell gewählt), `"choose"` („Choose a model“), `"none_linked"` („Link your model in the settings“).
- **Achtung, gefunden:** `StateMixin._save_state` (gui_state.py, Zeile 255) schreibt `state.json` nach jedem Lauf **komplett neu** aus einer festen Liste von Schlüsseln. Ein neuer Schlüssel wie `easy_mode` in `state.json` ginge dabei verloren. Deshalb gehört der Schalter nach `settings.json` (`cfgmod.get_setting` / `set_setting`), wie Favoriten und ausgeblendete Modelle.
- **Achtung, gefunden:** Läufe im Easy Mode würden über `_save_state` und `_remember_model_for_mode` die Einstellungen und die „Modell je Funktion“-Erinnerung des normalen Modus überschreiben. Das muss der Plan abfangen (Entscheidung 1.5).
- `test_gui_presets.py` stellt einen Tk-Stub bereit; `test_model_chip_menu.py` zeigt, wie man `grid`/`grid_remove` der Chips mitschreibt. Dasselbe Muster passt für Easy-Mode-Tests.

---

## 1. Was Easy Mode zeigt und versteckt

### 1.1 Welche Funktionen

| Funktion | Für Einsteiger? | Bemerkung |
|---|---|---|
| Text to image | ja | einfachste Funktion |
| Edit Canvas | ja | „make it night“; Tipp unter dem Prompt gibt es schon |
| Fill Selection | ja | Auswahl + Prompt; Fibo vorn im Ranking |
| Remove Selection | ja | Auswahl, Text optional |
| Expand image | eher ja | braucht das Crop-Werkzeug und weißen Rand (Tooltip erklärt es); für Einsteiger der schwierigste Ablauf |
| Upscale (new file) | ja | ein Klick; braucht den Upscale-Faktor oder einen festen Wert |
| Refine (same size) | eher nein | Prompt ist ein langer Standardtext, Unterschied zu Upscale schwer zu erklären |
| Multi Image Edit | nein | Slots, Tags, Describe, Cut out: das Gegenteil von „einfach“ |

- **Option A: sechs Funktionen** (Text to image, Edit, Fill, Remove, Expand, Upscale). Drei Reihen à zwei Knöpfe.
- **Option B: vier Funktionen** (Text to image, Edit, Fill, Remove). Am einfachsten, aber Expand und Upscale fehlen.
- **Option C: alle acht**, nur die Regler weg.
- **Empfehlung: A.** Refine und Multi Image Edit verschwinden; wer sie braucht, schaltet Easy aus.

### 1.2 Welche Bedienelemente

Bleiben sichtbar (Empfehlung):
- Kopf: Funktionsknöpfe (nur die aus 1.1), Minimieren.
- Generate mit „×n“ (Varianten), Cancel, Undo, Redo.
- Prompt mit Papierkorb; der orange Tipp unter dem Prompt (er erklärt jede Funktion schon heute).
- Upscale factor nur bei Upscale (oder fest, siehe unten).
- Fortschrittsbalken, Statuszeile, Live preview (wenn der Decoder da ist), Fußzeile mit ComfyUI-Punkt und Zahnrad.

Verschwinden:
- Modell-Chips (das Plugin wählt), Advanced settings ganz (Sharpen, Match colours, Context, Edge feather, Mask density, Layer mask, Show feather, Seam correction, Custom LoRAs, Steps, CFG, Seed, Sampler, Scheduler), Negative prompt, LLM-Zeile und LLM-Knopf, LoRA- und Stufen-Schalter (`f_opts`), Ready-made-Prompt-Schalter (Flux 2 Refine), „Set Page to Defaults“ (es gibt nichts zu verstellen).
- Offen: Verlauf (Uhr) und „Copy canvas“ im Kopf (siehe 1.4).

Upscale factor:
- **Option A:** die vier Schalter (1.5x, 2x, 3x, 4x) bleiben.
- **Option B:** fest 2x, kein Schalter.
- **Empfehlung: A** (ein Schalter mehr ist verständlich, „wie groß“ ist eine echte Wahl).

Eine „Qualität“-Wahl (z. B. `Fast` / `Best`):
- **Option A: keine.** Easy nimmt immer die Startwerte des besten Modells.
- **Option B: zwei Schalter `Fast` / `Best`**, die das Modell oder die Steps ändern. Dafür gibt es heute keine gemessenen Zeiten je Modell und Funktion (siehe 2.4); die Wahl wäre geraten.
- **Empfehlung: A** für die erste Fassung; B erst nach einer Zeitmessung je Funktion.

### 1.3 Was fest auf Standard steht

- **Option A: die Werkseinstellungen** der Funktion des gewählten Modells (`Mode.settings` in models.py), immer; gespeicherte Seiten (Rechtsklick „Save current settings“) gelten in Easy nicht.
- **Option B: gespeicherte Seite, falls vorhanden**, sonst Werkseinstellung (wie heute im normalen Modus).
- **Empfehlung: A.** Easy soll für jeden gleich und getestet sein (dieselbe Begründung wie deine Regel „Standardeinstellungen = Qualitätssicherung“). Seed immer zufällig, Varianten wie gewählt, LLM aus, Live preview an (wenn möglich).

### 1.4 Kopf: Verlauf und Copy canvas

- **Option A:** beide bleiben (sie stören nicht, sind nur Symbole).
- **Option B:** beide weg.
- **Option C:** Copy canvas bleibt, Verlauf weg (ein Verlaufseintrag lädt auch Modell und Regler, das passt nicht zu Easy).
- **Empfehlung: C.**

### 1.5 Was mit den Einstellungen des normalen Modus passiert

- **Option A: Merken (Schnappschuss).** Beim Einschalten von Easy speichert das Plugin Modell, Funktion und alle Fensterwerte (`_collect()`) in `settings.json` (`easy_return`); beim Ausschalten kommt genau dieser Stand zurück. Läufe in Easy schreiben weder `model_by_mode` noch die Fensterwerte des normalen Modus.
- **Option B: Nichts merken.** Beim Ausschalten bleibt das Modell, das Easy zuletzt gewählt hat, mit seinen Startwerten.
- **Option C: Zurücksetzen.** Beim Ausschalten „Set Page to Defaults“ für die Funktion.
- **Empfehlung: A.** Sonst verliert man beim Ausprobieren von Easy seine Einstellungen (Grund: `_save_state` und `_remember_model_for_mode` würden sie heute überschreiben, siehe Abschnitt 0). Prompt bleibt in beiden Modi derselbe (eine Prompt-Box).

### 1.6 Wie der Schalter aussieht und wo er sitzt

- **Option A: im Kopf**, links neben der Uhr, als kleiner Schalter im Stil der Upscale-Faktor-Schalter (`Small.Toolbutton`, orange wenn an), Text `Easy`. Immer sichtbar, ein Klick. Ändert den Fensterkopf, den du „perfekt“ nennst (darum nur mit deinem Ja).
- **Option B: in der Fußzeile**, neben „Live preview“, als Haken `Easy mode`. Kopf bleibt unberührt; Fußzeile wird voller (bei 380 px eng: ComfyUI-Punkt, Refresh, Set Page to Defaults, Live preview, Zahnrad). Im Easy Mode fällt „Set Page to Defaults“ weg, dann ist Platz.
- **Option C: nur im Zahnrad-Fenster** (eigener Reiter oder Haken oben in „Models“). Kein Platz im Hauptfenster nötig, aber schwer zu finden; Einsteiger kommen nicht zurück.
- **Option D: im leeren Kopfbereich `f_logo`.** Der ist für dein Bild reserviert; nicht empfohlen.
- **Empfehlung: A**, falls du den Kopf ändern willst; sonst **B**. Tooltip (Vorschlag): `Easy mode: only the basics. The plugin picks the best installed model and its tested settings. Click again for all settings.`

### 1.7 Erster Start für neue Nutzer

- **Option A: Easy ist beim allerersten Start an** (keine `settings.json` / kein `easy_mode`-Eintrag). Wer schon Einstellungen hat (du), startet wie bisher.
- **Option B: aus**, man schaltet selbst ein.
- **Option C: eine Frage beim ersten Start** (`Start in Easy mode?` Yes / No).
- **Empfehlung: A** (ein Einsteiger soll zuerst das einfache Fenster sehen; die Frage in C ist ein Fenster mehr).
- Zusatz zum leeren Zustand („Link your model in the settings“): im Easy Mode könnte dort ein Knopf `Get the starter models (19.8 GB)` stehen, der die Startermodelle aus Abschnitt 2 lädt (über den vorhandenen Download aus 14c). Optionen: **ja** (eigener Branch am Ende) / **nein** (nur der Hinweis auf das Zahnrad). **Empfehlung: ja, aber zuletzt** (Arbeitspaket 6), weil ein Startermodell gesperrt sein kann (Flux 3, siehe 2.3).

### 1.8 Wortlaut (Vorschläge, du entscheidest)

- Schalter: `Easy` (Kopf) oder `Easy mode` (Fußzeile).
- Leerer Zustand in Easy, wenn das beste Modell einer Funktion fehlt: `No model for this function yet. Get one in the settings (gear).`
- Zeile unter den Funktionsknöpfen (optional, gedämpft): `Model: Fibo 2.0 Edit Turbo (picked for you)`. Optionen: **zeigen** (man lernt, was läuft) / **nicht zeigen** (ruhiger). **Empfehlung: zeigen**, klein und grau, ohne Klick.
- Funktions-Tooltips: in Easy ohne die Zeile „Ranking: …“ vorn (die ist für deine Testphase), nur der allgemeine Text aus `models.FUNCTION_TIPS`.
- Status beim Umschalten: `Easy mode on: the plugin picks the model and settings.` / `Easy mode off: your settings are back.`

---

## 2. Minimales Modell-Set für Easy Mode

### 2.1 Was jedes Modell mit Standardeinstellungen braucht (aus manifest.py + inventory.mode_files)

Die Zahl ist die Summe aller Dateien, die das Plugin verlangt, bevor es das Modell überhaupt anbietet (alle Funktionen, Standardeinstellungen, inklusive Schalter, die beim Start an sind). Optionale Dateien (Vorschau-Decoder, LLM-Fallback, BiRefNet, SeedVR2, Upsampler) sind nicht mitgezählt.

| Modell | Download | Funktionen | Dateien | Laden |
|---|---|---|---|---|
| Flux 3 Klein | **11.3 GB** | T2I, Edit, Multi, Remove, Expand, Upscale | flux3 int8 5.83, qwen3vl_4b_int8 4.86, flux2-vae 0.34, Outpaint-LoRA 0.16, Restore-LoRA 0.16 | Hauptdatei **gesperrt** (Hugging-Face-Login + Lizenz), Plugin öffnet nur die Seite |
| Fibo 2.0 Edit Turbo | **13.6 GB** | T2I, Edit, Multi, Refine, Fill, Expand, Remove | fibo2 int8 8.41, qwen3vl_4b_int8 4.86, flux2-vae 0.34 | alles direkt |
| MOSS | **13.1 GB** | nur T2I | moss int8 5.41, qwen3.5_9b_w4a8 7.34, flux2-vae_small 0.25, Lenovo-LoRA 0.06 | alles direkt |
| Qwen 2.1 | **17.3 GB** | T2I, Edit, Multi, Fill, Expand, Remove | qwen 2.1 int8 7.26, qwen3vl_8b_int8 9.35, VAE 0.68 | alles direkt |
| Flux 2 Klein | **18.6 GB** | T2I, Edit, Multi, Remove, Expand, Upscale, Refine | flux2 int8 9.44, qwen_3_8b_fp8mixed 8.66, flux2-vae 0.34, UltraReal-LoRA 0.17 | UltraReal von **Civitai** (Browser, evtl. Login); ohne sie ist Flux 2 ganz gesperrt (Upscale/Refine starten mit ihr) |
| Krea 2 | 19.0 GB | nur T2I | – | alles direkt |

Geteilte Dateien: Flux 3 und Fibo teilen `qwen3vl_4b_int8_convrot` und `flux2-vae` (zusammen 5.2 GB). Deshalb ist das Paar so klein.

Wichtig für Upscale: Nur Flux 2 und Flux 3 können Upscale, und **beide** brauchen eine Datei, die das Plugin nicht selbst laden kann (Flux 3: gesperrt bei Hugging Face; Flux 2: Civitai). Ein Set mit Upscale ist also nie ganz automatisch ladbar.

### 2.2 Kandidaten

| Set | Download | Deckt ab (von 8) | Fehlt | Bester Weg je Funktion in Easy | Automatisch ladbar? |
|---|---|---|---|---|---|
| **S1 Ein Allrounder: Fibo** | **13.6 GB** | 7 | Upscale | Fill, Remove: Fibo (Rang 1); Edit: Fibo („perfekt“); Expand: Fibo (Rang 4); T2I: Fibo (nicht bewertet); Refine: Fibo | ja, alles |
| **S2 Kleinstes Komplett-Set: Flux 3 + Fibo** | **19.8 GB** | 8 | – | T2I: Flux 3 („perfekt“); Edit: Flux 3 oder Fibo (beide „perfekt“); Fill, Remove: Fibo (Rang 1); Expand: Flux 3 (Rang 2); Upscale: Flux 3 („perfekt“); Refine: Fibo | nein: Flux 3 braucht einmal Hugging-Face-Login + Lizenz |
| **S3 Ohne Hugging-Face-Login: Flux 2 + Fibo** | **31.9 GB** | 8 | – | Expand: Flux 2 (Rang 1); Fill, Remove: Fibo; Edit: Flux 2 oder Fibo („perfekt“); T2I, Upscale, Refine: Flux 2 oder Fibo (nicht bewertet) | nein: UltraReal-LoRA über Civitai im Browser |
| S4 Deine „perfekten“ Modelle: Flux 3 + Qwen + Fibo | 37.0 GB | 8 | – | wie S2; Qwen käme in Easy nur zum Zug, wenn es in einem Ranking vorne steht (heute nirgends vor Fibo bzw. Flux 3) | nein (Flux 3) |
| (S5 zum Vergleich: Flux 3 + Qwen) | 28.6 GB | 7 | Refine | Fill, Remove, Expand: Qwen („perfekt“, Rang 2); Rest Flux 3 | nein (Flux 3) |

Nicht sinnvoll für Easy: MOSS (nur Text to image; Flux 3 Text to image ist auch „perfekt“) und Krea 2 (nur Text to image, 19 GB).

**Empfehlung: S2 (Flux 3 + Fibo, 19.8 GB)** als „Startermodelle“: alle acht Funktionen, für sieben davon ein Modell, das du „perfekt“ nennst oder auf Rang 1/2 setzt, und das kleinste Komplett-Set. Nachteil: ein Login-Schritt bei Hugging Face. Wenn das für Einsteiger zu viel ist: **S1 (nur Fibo, 13.6 GB)**, ohne Upscale, ganz automatisch; Flux 3 dann als „optional für Upscale und bessere Bilder aus Text“.

Lizenzen (für die Doku, nicht neu geprüft): Fibo CC BY-NC 4.0 und die FLUX.2-Dateien nur nicht-kommerziell; Flux 3 FLUX Kommunity License; Qwen Forschungslizenz; MOSS Apache 2.0.

### 2.3 Regel „ganzes Modell gesperrt“ und Easy

- Easy nimmt je Funktion das am höchsten gerankte Modell, das **angeboten** wird (`_model_usable`: alle Funktionen des Modells haben ihre Standard-Dateien) und nicht ausgeblendet ist. Die Regel bleibt also unverändert; Easy verlässt sich auf sie.
- Beispiel: Fehlt bei Flux 3 nur die Restore-LoRA (Upscale), ist Flux 3 ganz gesperrt, auch für Text to image und Expand. Easy fällt dann auf das nächste Modell im Ranking zurück (Expand: Qwen oder Fibo), Upscale ist grau.
- Hat keine angebotene Funktion ein Modell, zeigt Easy den leeren Zustand (1.8).

### 2.4 Tempo und VRAM: was das Repo belegt

- Gemessen ist nur 16 GB VRAM (RTX 4070 Ti Super, 64 GB RAM, int8-ConvRot-Dateien); alles andere ist **nicht gemessen** (`PLAN.md` 14d, `docs/openfill-modellmanager.md`: keine offiziellen Zahlen für 8 oder 12 GB; int8 braucht eine Grafikkarte ab Turing).
- Belegte Zeiten: Flux 3 Expand mit Outpaint-LoRA Median **10 s** je Lauf (`docs/tests/flux3-expand-lora.md`); MOSS Text to image mit 35 Steps / CFG 3.0 **ca. 30 s** je Bild (`docs/tests/moss-cfg.md`); Fibo-LLM-Schreiber **ca. 20 s extra** (in Easy aus).
- Nicht gemessen: Zeiten von Fibo (Fill, Remove, Edit, Expand, Text to image), Flux 3 Text to image / Edit / Upscale, und wie lange der Wechsel zwischen Flux 3 und Fibo dauert (ComfyUI lädt das andere Diffusionsmodell; Text-Encoder und VAE sind dieselben, das spricht für einen schnelleren Wechsel, ist aber **nicht gemessen**).

---

## 3. Technischer Plan

### 3.1 Wo der Code hinkommt

- **`pccomfy/easymode.py` (neu, ohne Tk):** reine Logik, damit sie ohne Fenster testbar ist.
  - `EASY_MODES = ("txt2img", "edit", "inpaint", "remove", "outpaint", "upscale")` (je nach Entscheidung 1.1).
  - `best_model(mode, usable, hidden, favorites) -> str`: Ranking aus `models.RANKING`, dann (Option, siehe 3.3) feste Reihenfolge; nur Modelle, die die Funktion haben, `usable(key)` sind und nicht ausgeblendet.
  - `start_settings(model_key, mode) -> dict`: die Werkseinstellungen (`Mode.settings` plus die Regeln aus `_apply_model_mode`: `match`/`sharpen` 0, Context, Mask density, `enhance` False, Seed -1), ohne `cfgmod.saved_page`.
  - Texte (Schalter, Tooltip, Status, leerer Zustand) als Konstanten; `user-edits.md` bekommt die Datei als neuen Ort für sichtbare Texte (Regel aus CLAUDE.md).
  - Speichern: `is_on()` / `set_on(bool)` / `save_return(dict)` / `pop_return()` über `cfgmod.get_setting` / `set_setting` (Schlüssel `easy_mode`, `easy_return` in `settings.json`; **nicht** `state.json`, siehe Abschnitt 0).
- **Fenster-Teil: Option A `pccomfy/gui_easy.py` mit `EasyMixin`** (CLAUDE.md: neue Methode in den Mixin ihres Themas; Easy ist ein neues Thema). Der Mixin steht in `class App(...)` **vorn** und überschreibt mit `super()`-Aufruf: `_update_mode_radios` (nur Easy-Funktionen griden), `_update_model_chips` (alle Chips `grid_remove`), `_on_mode_ui` und `_apply_start_state` (danach `_easy_hide()`), `_model_for_mode` (Easy-Auswahl), `_remember_model_for_mode` und `_save_state` (in Easy nichts in den normalen Zustand schreiben). **Option B:** ein Flag `self._easy` und `if`-Zweige direkt in gui_modes.py / ui_settings.py / gui_state.py. **Empfehlung: A** (ein Ort, die „perfekten“ Teile bleiben unverändert, ausgeschaltet verhält sich alles wie heute).
- **Verstecken:** `_easy_hide()` ruft `pack_forget` / `grid_remove` auf `f_models`, `f_adv`, `f_neg`, `f_enh`, `f_opts`, `b_llm`, `f_pchoice`, `b_reset`, `b_history` und auf die Funktionsknöpfe außerhalb `EASY_MODES`. Weil `_on_mode_ui`, `_show_enhance_box`, `_update_options_box`, `_show_advanced`, `_apply_start_state` und die Slots (refslots.py) Teile wieder einpacken, läuft `_easy_hide()` jeweils **nach** ihnen (Überschreibung im Mixin), danach `_fit_height()`. `_easy_show()` beim Ausschalten: die normalen Methoden einmal aufrufen (`_apply_start_state`, `_update_mode_radios`, `_on_mode_ui`, `_show_advanced`, `_show_negative`), sie packen alles in der richtigen Reihenfolge wieder ein.
- **Schalter:** in `_build` (gui.py) ein `ttk.Checkbutton` / Toolbutton mit `v_easy` an der Stelle aus 1.6; Befehl `toggle_easy()` im Mixin.
- **Modellwahl in Easy:** `_on_mode` ruft heute `_model_for_mode` nur, wenn das gewählte Modell die Funktion nicht kann. In Easy soll **jeder** Funktionswechsel das beste Modell nehmen: der Mixin setzt in `_on_mode` vorher `v_model` auf `best_model(...)` und ruft dann `_on_model` (das setzt die Startwerte über `_apply_model_mode(force=True)`). `cfgmod.saved_page` muss in Easy übersprungen werden (Entscheidung 1.3): kleiner Haken in `_apply_model_mode`, z. B. `if not getattr(self, "_easy", False): s.update(cfgmod.saved_page(...))`. Das ist die einzige Änderung in einer bestehenden Methode, die ich nicht vermeiden kann.
- **Inventar-Updates:** Nach `_set_inventory` (neue Dateien, ComfyUI neu gelesen) wählt Easy das beste Modell neu, falls sich die Liste geändert hat und kein Lauf läuft.

### 3.2 Arbeitspakete (je ein Branch von `next`, in dieser Reihenfolge)

| Nr. | Branch | Inhalt | Test |
|---|---|---|---|
| 0 | (kein Code) | deine Antworten auf Abschnitt 4, Ranking für Text to image, Edit, Upscale, Refine | – |
| 1 | `feat/ranking-all-functions` | `models.RANKING` um deine Reihung ergänzen (wirkt sofort im Tooltip „Ranking: …“) | `tests/test_ranking.py` neu oder Erweiterung eines bestehenden Tests: jeder Schlüssel im Ranking ist ein Modell, das die Funktion hat |
| 2 | `feat/easymode-core` | `pccomfy/easymode.py` ohne Tk: `EASY_MODES`, `best_model`, `start_settings`, Einstellungs-Schlüssel | `tests/test_easymode.py` (rein Python, Fake-`usable`): bestes Modell je Funktion für S1, S2, S3; gesperrtes Modell wird übersprungen; ausgeblendetes auch; keine Funktion ohne Modell → `""` |
| 3 | `feat/easymode-switch` | `gui_easy.py` (`EasyMixin`), Schalter, Verstecken/Zeigen, `_fit_height` | `tests/test_easymode_gui.py` mit dem Stub aus `test_gui_presets.py` und dem Mitschreiben von `grid`/`pack` wie in `test_model_chip_menu.py`: an = Chips, Advanced, Negativ, LLM-Zeile weg, nur `EASY_MODES` gegridet; aus = alles wie vorher |
| 4 | `feat/easymode-model-pick` | Modellwahl je Funktion, Werkseinstellungen ohne gespeicherte Seite, Zeile „Model: … (picked for you)“, Tooltips ohne Ranking | im selben Testfile: Funktionswechsel setzt das beste Modell und dessen `Mode.settings`; `saved_page` greift nicht |
| 5 | `feat/easymode-state` | Schnappschuss `easy_return`, kein Schreiben in `model_by_mode` / `state.json`-Fensterwerte während Easy, Zustand über Neustart | Test: normal einstellen → Easy an → Lauf (Fake) → Easy aus → alte Werte und altes Modell zurück; Neustart mit `easy_mode` = true startet in Easy |
| 6 | `feat/easymode-first-start` | Easy beim ersten Start an (falls gewählt), leerer Zustand mit Text, optional Knopf „Get the starter models“ (nutzt `ui_downloads`, bei Flux 3 öffnet er die Seite) | Test mit leerem `PCCOMFY_HOME` und `PCCOMFY_SIMULATE_NO_MODELS`-artigem Inventar |
| 7 | `docs/easymode` | `user-edits.md` (neue Textdatei `easymode.py`), `PLAN.md`, `docs/erledigt.md`, README nur auf deinen Wunsch | `python tests/run_all.py` (dann 76 oder 77 Dateien) |

Jedes Paket: Tests grün, `git merge --no-ff` nach `next`, Bericht auf Deutsch.

### 3.3 Kleinere technische Entscheidungen

- **Funktion ohne Ranking (falls du nicht alle rankst):** Option A: feste Reihenfolge `models.MODELS` (Flux 3, Flux 2, Qwen, Fibo, Krea 2, MOSS); Option B: Funktion in Easy ausblenden, bis sie ein Ranking hat. **Empfehlung: A**, damit Easy sofort benutzbar ist.
- **Favorit (Rechtsklick) in Easy:** Option A: Favorit schlägt das Ranking (wie im normalen Modus); Option B: Easy ignoriert Favoriten. **Empfehlung: B** (Easy = deine geprüfte Reihung, für alle gleich; der Rechtsklick ist in Easy ohnehin nicht erreichbar, weil die Chips weg sind).
- **Ausgeblendete Modelle (Hide):** Easy hält sich daran (ein ausgeblendetes Modell wird nie gewählt). Empfehlung so lassen.

### 3.4 Risiken

- **Fensterkopf „perfekt“:** Schalter im Kopf ändert ihn (1.6). Nur mit deinem Ja.
- **Teile tauchen wieder auf:** viele Stellen packen Rahmen neu ein (`_on_mode_ui`, `_pack_post`, `_show_enhance_box`, `_update_options_box`, Slots, `_apply_start_state`). Jede neue Stelle in Zukunft muss Easy beachten. Gegenmittel: ein Test, der nach jedem Funktionswechsel prüft, dass nichts Verstecktes sichtbar ist.
- **Zustand überschrieben:** ohne Paket 5 verliert man normale Einstellungen (`_save_state` schreibt alles neu).
- **Gesperrte Downloads:** Flux 3 braucht Login; Einsteiger scheitern dort am ehesten. Darum S1 als Rückfall.
- **Kein Ranking für fünf Funktionen:** ohne deine Reihung wählt Easy dort nach fester Reihenfolge, nicht nach Qualität.
- **Modellwechsel kostet Zeit:** Easy springt je Funktion zwischen Modellen (bei S2 Flux 3 ↔ Fibo). Ladezeit nicht gemessen.
- **Expand für Einsteiger:** der Ablauf mit Crop-Werkzeug und weißem Rand bleibt schwierig, auch mit Tipp.

### 3.5 Was du live prüfen musst (ich kann es nicht)

- Aussehen im echten Fenster bei 100 % und 150 % Skalierung: Easy an/aus, Höhe passt sich an, nichts bleibt hängen, kein Flackern.
- Hin- und Herschalten mit offenen Advanced settings und offenem Negativ-Prompt; danach ist alles wie vorher.
- Neuer Nutzer: `photocraft-ai neuer-nutzer.bat` (mit und ohne `PCCOMFY_SIMULATE_NO_MODELS=1`): startet in Easy (falls gewählt), leerer Zustand, Starter-Knopf.
- Je Easy-Funktion ein echter Lauf mit dem gewählten Modell (GPU, nur mit deiner Erlaubnis), um zu sehen, dass die Werkseinstellungen ankommen (`data/exchange/last-graph.json`).
- Zeit beim Wechsel Flux 3 ↔ Fibo (wenn du S2 nimmst).

---

## 4. Offene Fragen an dich (nach Wichtigkeit)

1. **Ranking** für Text to image, Edit Canvas, Upscale (und Refine, falls es bleibt): welches Modell zuerst? (Vorschlag aus deiner „perfekt“-Liste: Text to image Flux 3, MOSS; Edit Flux 3, Qwen, Flux 2, Fibo; Upscale Flux 3, Flux 2; Refine Fibo, Flux 2.)
2. **Funktionen in Easy:** sechs (Empfehlung), vier oder alle acht? (1.1)
3. **Wo sitzt der Schalter:** Kopf neben der Uhr (ändert den „perfekten“ Kopf), Fußzeile oder Zahnrad? (1.6)
4. **Startermodelle:** S2 Flux 3 + Fibo (19.8 GB, ein Hugging-Face-Login) oder S1 nur Fibo (13.6 GB, ohne Upscale, ganz automatisch)? (2.2)
5. **Beim Ausschalten:** normale Einstellungen zurück (Schnappschuss, Empfehlung), oder bleibt Easys Wahl? (1.5)
6. **Erster Start neuer Nutzer:** Easy an (Empfehlung), aus, oder fragen? Und soll es den Knopf „Get the starter models“ geben? (1.7)
7. **Gespeicherte Seiten und Favoriten:** in Easy ignorieren (Empfehlung) oder nutzen? (1.3, 3.3)
8. **Zeile „Model: … (picked for you)“** unter den Funktionen zeigen oder nicht? Und der genaue Wortlaut der Texte in 1.8.

---

## 5. Was ich nicht prüfen konnte

- Kein Fenster gestartet, keine Generierung; alle Aussagen zum Verhalten stammen aus dem Code.
- Ob alle sechs Easy-Funktionen mit den Werkseinstellungen bei Fibo bzw. Flux 3 so gut sind wie im normalen Modus: nur so gut wie deine bisherigen Tests (Fibo Text to image ist von dir nicht bewertet; Fibo Expand ist Rang 4).
- Lizenzen nicht neu geprüft (aus `manifest.py` und `docs/model-downloads.md` übernommen).
- Die Zahl der Testdateien (heute 74) steigt durch die Pakete 1 bis 6 auf ca. 76 bis 77.
