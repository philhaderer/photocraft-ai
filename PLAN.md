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

Alles gebaut und in `next`, mit Tests; im echten Fenster noch nicht von dir geprüft.

**Neu vom 30.10.**
- **Fill-Masken-Testrunde, Stufe 2:** starten, blind bewerten, auswerten (drei Befehle in `docs/tests/fill-mask-testrunde.md`).
- **Verlauf der letzten 20 Läufe (Punkt 13):** Uhr-Symbol im Header links von „Copy canvas“; die Liste zeigt „Uhrzeit  Name · Modell: Prompt-Anfang“. Ein Klick lädt alle Einstellungen des Laufs mit neuem Seed und startet nichts; hat das LLM den Prompt geschrieben, kommt dessen Text zurück und Enhance ist aus. Strg+Z im Prompt-Feld holt den alten Text zurück. Abgebrochene und fehlerhafte Läufe kommen nicht in die Liste.

**Neu vom 29.10.**
- **L3 Fenster-Politur (Punkt 11):** Doppelklick auf den Header klappt ein und aus; Rechtsklick auf einen Modell-Chip: „Favourite for <Funktion>“ (Haken im Menü) und „Hide this model“; im Zahnrad-Fenster, Tab „Models“, Haken „Shown in the plugin“; Symbol „Copy canvas“ im Header (sichtbare Ebenen als ein Bild in die Zwischenablage).
- **Live-Vorschau (Punkt 12):** läuft sie je Modell? Fenster bei 380 px? Haken „Live preview“ am Ende der Advanced settings. Später: A/B grobe Farben gegen TAESD-Dateien (Download nur mit deiner Erlaubnis).
- **Describe mit Zufalls-Seed:** zweimal hintereinander auf demselben Slot gibt einen neuen Text; sonst kommt die alte Beschreibung ohne neuen Lauf. Dazu: letzte Beschreibung weiß an der Stelle der orangen Meldung mit Kopier-Symbol; Tag unter dem Slot weiß in dunkler Box.
- **Seam-Korrektur je Modell:** Fibo korrigiert immer (eine Ebene, ohne „[raw]“); Flux 2/3 nie; Qwen und eigene Workflows mit dem Haken „Seam correction (A/B)“.
- **Flux 3 Expand mit Outpaint-LoRA:** Bilder aus dem A/B-Test bewerten (`docs/tests/flux3-expand-lora.md`) und im echten Fenster prüfen.
- **Fensterkopf und Fußzeile:** Header mit Minimieren-Knopf (eingeklappt bleibt nur der Header, Chevron zum Aufklappen); Refresh als ⟳ neben dem ComfyUI-Punkt, „Defaults“ als Textknopf (Abstände, Größe bei 150 %).
- **Kleinere Punkte:** Prompt-Box hüpft nicht mehr beim Größerziehen; kein Flackern bei wenig Platz; Upscale factor als vier Schalter 1.5x bis 4x; Prompt-Auswahl (z. B. Flux 2 Refine „Default“) als kleine Schalter; Context in Prozent; Checkbox im PhotoCraft-Look (orange angehakt); Seed in den Advanced settings; Variants als „×2 ▾“ am Generate-Knopf; Pfeile der Zahlenfelder größer; Prompt-Feld mit dünnem Scrollbalken; Tipp mit orangem Info-Symbol.
- **Slots (Multi Image Edit):** Auge öffnet die Vorschau neben dem Plugin; Bild aus einem Slot in die Prompt-Box ziehen fügt das Tag dort ein, wo man loslässt; Klick auf das Tag hängt es ans Prompt-Ende; Slot-Symbole kleiner (19 px); Hinweis nennt `<image1>` für das PhotoCraft-Bild.

**Älter (28.10.), noch nicht ausdrücklich bestätigt**
- **Zahnrad-Fenster (Punkt 15a):** „Choose another file…“ → Relink, Undo, Reset to startup; Tabs „Models“ und „Credits“.
- **Mask density:** Fill mit Qwen und Fibo startet bei 5 % (PhotoCraft 0.17+). Danach willst du ihn auch bei anderen Funktionen (z. B. Expand) ausprobieren.
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
- Fensterkopf: Funktion zuerst (große Buttons mit Symbol), Modelle darunter als Chips. Minimieren = Einklappen zum Header (Knopf oder Doppelklick).
- Rechtsklick auf Modell-Chip: Favorit (Haken im Menü, kein Zeichen am Chip), Modell ausblenden; zurückholen nur im Zahnrad-Fenster. Workflow-JSON speichern verworfen.
- Settings-Fenster mit Tabs „Models“ und „Credits“; weitere Tabs später.
- Strg+Z/Strg+Y bleiben wie heute (kein Plugin-Kürzel). Tooltips bei jedem Start.
- Fortschrittsbalken bleibt orange. Runde Radios gibt es nicht (PhotoCraft hat keine), stattdessen kleine Schalter.

**Masken und Regler**
- Layer mask nur soft / hard / none. Fill Qwen/Fibo „soft“ = Auswahl voll deckend, weicher Rand nur außen.
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
14. **Modell-Manager von OpenFill vergleichen** (T4): sobald du das Repo geladen hast; Ergebnis als Gegenüberstellung mit Empfehlung (übernehmen / anpassen / weglassen).

**Offen aus den Testrunden**
- **Fill-Maske neu** (Befund 28.10.): die schmale weiche Kante schneidet bei Fill den Rand der Füllung und ihren Schatten ab. Ein erster Versuch (Maske läuft bis zum Rand des Ausschnitts aus) war „viel besser“, wurde aber zurückgenommen (an Bildkanten weich, ohne Regler nicht testbar). **Testrunde gebaut 30.10.** (`docs/tests/fill-mask-testrunde.md`): vier Masken-Varianten (heute schmal, heute Dichte 5 %, bis zum Ausschnittrand, breit 3×). Stufe 1 ohne GPU erledigt: Alle halten die Regeln ein, keine läuft an einer Bildkante aus. **Stufe 2 wartet auf dich:** 40 echte Läufe (auf ein Viertel gekürzt, ca. 12–15 Min.), dann alle 40 Fälle blind bewerten. Danach baue ich den Sieger ein.
- **Tooltip zur runden Auswahl:** ob einer dazukommt, ist offen.
- **Ranking** für die noch offenen Funktionen (Abschnitt 2), wenn du es nennst.

**Danach**
15. **Flux-3-Boxen** (Entscheidung offen: A Textlauf von `Flux3LayoutPrompt` zuerst, B Knoten in den Workflow, C nur von Hand; Notizen `docs/flux3-bbox-workflow-notes.md`).
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
