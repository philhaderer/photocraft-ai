# PLAN: PhotoCraft x ComfyUI plugin, release 1

Stand 2026-10-27. Der Plan ist freigegeben. **Gebaut und in `next` gemergt:** Phase 0, Lane L1 (Erkennung/Settings), Lane L2 (Multi Image Edit, Runden 1 bis 3) und die erste UI-Runde vom 26./27.10. (Icons, Slider, Slot-Fixes, Downloadlinks; Details im Handoff). **Als Nächstes:** die Aufgabenliste in Abschnitt 8 (kleine Verbesserungen zuerst, dann weiter nach Plan). **Offen:** L3 (Fenster-Politur), L4 (Inhalte), Flux-3-Boxen (Entscheidung offen), Easy Mode zuletzt. Aktueller Gesamtstand und offene Entscheidungen: `docs/HANDOFF-claude-code.md`. Backup: Tag `backup-2026-10-26` (6df02df) und das ZIP des Users.

## 1. Entscheidungen des Users (26.10.)

- Fill für Flux später. Easy-Mode-Ranking Fill: Qwen, Fibo.
- Krea 2 Expand und Flux 3 Expand werden deaktiviert (am 26.10. abends für einen neuen Test wieder eingeschaltet; nach dem Test entscheidet der User). Easy-Mode-Ranking Expand: MOSS, Flux 2, Fibo, Qwen.
- Tutorial-PSDs: nur Testbild, ohne Referenzbilder; eigener Modus später.
- Repo: Option c (neues Repo ohne Upstream-Verlauf, Credits bleiben Pflicht), Zeitpunkt b: erst kurz vor dem Veröffentlichen. Bis dahin Branch `windows-fibo`.
- Release 1: nur 16 GB getestet, 8-GB-Empfehlungen als Doku. AusBoss behalten und als Abhängigkeit deklarieren.
- Remove: Formulierungen für den Tipp unter dem Prompt testen, keine Automatik.
- Drag and Drop mit `tkinterdnd2`, Ctrl+V zusätzlich. Minimize = einklappen zur Titelleiste, Button „hide“/„show“.
- Slots: Stift nur im Slot (nicht im Viewer); birefnet-Workflow für „Remove background“; Slotzahl je Modell begrenzt, Slotbreite überall gleich; erst prüfen, ob Qwen 3.5 9B Bilder liest.
- Fast Mode gestrichen. „(1 doc.)“ unten entfernen, „Done.“ grün und linksbündig. ComfyUI-Punkt existiert schon (erledigt).
- Undo/Redo: Funktion bleibt, Buttons mit `undo.png` des Users (Redo gespiegelt).
- Tooltips bei jedem Start. Krea-Styles: Repo klonen, Bilder wählt der User (max. 50), Prompt-Templates per Klick; später evtl. MOSS.
- Rechtsklick auf Modell-Tab: als Favorit setzen (Easy-Mode-Vorrang), Tab ausblenden, Workflow-JSON mit allen Settings speichern.
- Reihenfolge: Modell-Erkennung (Settings, Preflight, graue Modelle) zuerst, Easy Mode zum Schluss.

## 2. Ausgangslage: warum Branches kollidieren

| Datei | Zeilen | Befund |
|---|---|---|
| `pccomfy/gui.py` | 2265 | Eine Klasse `App`; `_build` allein 350 Zeilen. Fast jedes Feature fasst sie an. |
| `pccomfy/bridge.py` | 1075 | Lauf-Logik, Export/Import, Undo. |
| `pccomfy/workflows.py` | 721 | Graph-Anpassung, LoRA, Slots. |
| `pccomfy/models.py` | 187 | Registry der Tabs und Modi (kleine, heiße Datei). |
| `workflows/*.json` | 14 | Je Workflow eine Datei, selten gemeinsam berührt. |

Folge: ohne Umbau würden alle Lanes dieselbe Datei ändern. Deshalb gibt es Phase 0.

## 3. Konfliktmatrix (x = ändert die Datei, n = neue Datei)

| # | Aufgabe | gui.py | bridge.py | workflows.py/json | models.py | config/comfy | neu | Lane |
|---|---|---|---|---|---|---|---|---|
| 1 | Krea 2 / Flux 3 Expand aus | | | | x | | | 0 |
| 2 | „(1 doc.)“ weg, Done grün links | x | | | | | | 0 |
| 3 | `gui.py` in Mixins teilen (kein Verhalten ändern) | x | | | | | n | 0 |
| 4 | Gemeinsame Felder in `Model`/`Mode` (max_refs, tag_style) | | | | x | | | 0 |
| 5 | `clipboard.py` (Bild lesen und schreiben) | | | | | | n | 0 |
| 6 | Modell-Erkennung, Manifest, Preflight | x (Hook) | | | | x | n | L1 |
| 7 | Settings-Overlay (Zahnrad, yaml-Drop, Refresh, Contributors) | x | | | | x | n | L1 |
| 8 | Graue Tabs + „set in settings“ | x (Hook) | | | | | | L1 |
| 9 | Multi Image Edit: Slot-Widget, Drop, Ctrl+V | x (Hook) | | | | | n | L2 |
| 10 | Multi Image Edit: Export, Tags je Modell | | x | x | x | | | L2 |
| 11 | Multi Image Edit: Referenz-Slots Flux 2/3, Qwen, Fibo | | | x (json) | | | | L2 |
| 12 | birefnet-Workflow „Remove background“ | | x | x (json) | | | n | L2 |
| 13 | Qwen 3.5 9B beschreibt Referenzbilder (nach Prüfung) | | x | x | | | | L2 |
| 14 | Hide/Show-Button, PhotoCraft-Look der Slider/Haken | x | | | | | n | L3 |
| 15 | Undo/Redo-Buttons (`undo.png`), Copy canvas to clip | x | x | | | | | L3 |
| 16 | Rechtsklick-Menü (Favorit, ausblenden, JSON speichern) | x | x | | | x | | L3 |
| 17 | Krea-Style-Chooser | x (Hook) | | | | | n | L4 |
| 18 | Tipps, tägliche Tooltips, Tutorial-PSDs | x (Hook) | | | | | n | L4 |
| 19 | Easy Mode | x | | | x | x | n | zuletzt |
| 20 | Test-Runner `tests/run_all.py`, Tests je Lane | | | | | | n | alle |

„x (Hook)“ heißt: nur eine Zeile in der Zusammensetzung der Fenster-Klasse; der Inhalt steckt in der neuen Datei.

## 4. Phasen und Lanes

**Phase 0 (erledigt 2026-10-26, in `next`; Aufgaben 1 bis 5 und 20; dazu `requires` in `Model`):** Aufgaben 1 bis 5 und 20. Branch `refactor/split-gui`.
- `gui.py` bleibt als Einstieg, `App` erbt von Mixins (Prompt, LoRA, Modell/Modus, Zustand/Presets, Lauf/Fortschritt, Theme). Kein Verhalten ändert sich; alle 31 Tests müssen vorher und nachher grün sein.
- `models.py` bekommt alle neuen Felder auf einmal, damit keine Lane die Dataclass anfasst.
- `clipboard.py` wird jetzt gebaut, weil L2 (lesen) und L3 (schreiben) es beide brauchen.

**Danach, höchstens zwei Lanes gleichzeitig** (dein Live-Test ist der Engpass):

| Lane | Besitzt (nur diese Lane ändert sie) | Reihenfolge |
|---|---|---|
| L1 Erkennung/Settings (**erledigt, in `next`**) | `inventory.py`, `manifest.py`, `ui_settings.py`, `config.py`, `comfy.py` | zuerst |
| L2 Multi Image Edit (**erledigt, Runden 1 bis 3, in `next`**) | `refslots.py`, `bridge.py`, `workflows.py`, `workflows/*.json`, `models.py` | parallel zu L1 |
| L3 Fenster-Politur | Theme-Mixin, Titelleiste, Menü, Icons | nach L1 oder L2 |
| L4 Inhalte | `styles.py`, `tips.py`, Daten, Beispiele, `docs/` | jederzeit (nur neue Dateien) |
| Easy Mode | `easymode.py` | zuletzt, braucht L1, L2, Hide/Show aus L3 |

Berührungspunkte nur über feste Schnittstellen: `models.py` (nur L2, danach nur über Felder aus Phase 0), `config.py` (nur L1; Favoriten und ausgeblendete Tabs gehen über eine kleine Funktion, die L1 anbietet), `bridge.py` (nur L2; L3 ruft nur bestehende Funktionen).

## 5. Git-Ablauf (du musst nichts davon bedienen)

- `windows-fibo` bleibt der Stand, den du abgenommen hast. Neuer Branch `next` ist der Integrationsstand, **den du testest**.
- Je Aufgabe ein Branch (`feat/...`, `fix/...`) aus `next`. Vor dem Zusammenführen laufen alle Tests (`python tests/run_all.py`). Danach Merge in `next`, nie zwei Merges gleichzeitig, nie Push.
- Arbeitsweise seit dem Umstieg auf Claude Code (Entscheidung 2026-10-26): eine Claude-Code-Sitzung arbeitet Branch für Branch direkt im Repo und mergt nach grünen Tests in `next`. Keine Lane-Chats und kein FRAGEN/ANTWORTEN-Ablauf mehr; Fragen stellt die Sitzung direkt im Chat. Sollen zwei Aufgaben wirklich parallel laufen, dann per `git worktree` statt eigener Klone.
- Altlast: `lanes/L1`, `lanes/L2` sind eigenständige Klone (per `.git/info/exclude` ignoriert), vollständig in `next` gemergt und werden nicht mehr benutzt. Archiv der Fragen und Antworten: `docs/archiv-lanes/`.
- Wenn du ein Ergebnis abgenommen hast, wird `windows-fibo` auf `next` vorgezogen. Das neue Repo entsteht erst vor dem Veröffentlichen.
- Commits nach Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, Details in `CLAUDE.md`), Trailer `Co-Authored-By: Claude <Modell der laufenden Sitzung> <noreply@anthropic.com>` (z. B. `Claude Opus 5.5`).

## 6. Wann ein neuer Chat sinnvoll ist

- Wenn Regeln vergessen werden, Antworten sich wiederholen oder ein Chat sehr lang wird.
- Bei einem größeren Themenwechsel (z. B. nach Abschluss von L3) kann eine frische Sitzung sinnvoll sein; sie liest `CLAUDE.md`, `PLAN.md` und `docs/HANDOFF-claude-code.md`.

## 7. Risiken und offene Punkte

- `tkinterdnd2` ist eine neue Abhängigkeit (Setup-Skript und README-Windows erweitern). Funktioniert es mit deinem Python? Vorher ausprobieren.
- „Workflow-JSON speichern“: unsere Workflows sind API-Format. Ob dein ComfyUI-Frontend es per Drag-and-drop lädt, ist ungeprüft; sonst braucht es eine Umwandlung ins Editor-Format.
- `undo.png` liegt in `pccomfy/assets/undo.png` (getrackt, package-data in `pyproject.toml`). Zur Laufzeit mit Pillow klein skalieren und für Redo spiegeln; das Icon ist schwarz und muss für den dunklen Hintergrund eingefärbt werden.
- In der VM gibt es kein tkinter: das echte Fenster rendert nur bei dir. Tests laufen gegen gestubbtes Tk.
- Krea-Style-Explorer: Lizenz des Repos und der Bilder vor dem Mitliefern klären (Klonen zum Ansehen ist okay).
- Scribble/Sketch, Remove-Prompt, Encoder-Tausch, Steps-Prüfung: Recherche- und Testaufgaben ohne Code, getrennt von den Lanes (`docs/tests/`).
- Easy-Mode-Ranking ist ein Datensatz in `easymode.py`; „Favorit“ aus dem Rechtsklick überschreibt ihn je Funktion.

## 8. Aufgabenliste des Users vom 27.10. (Reihenfolge: kleine Verbesserungen zuerst, dann weiter nach Plan)

Wortlaut des Users sinngemäß übernommen; Details, Befunde und Optionen stehen im Handoff, Abschnitt 6.

**A. Kleine Verbesserungen (zuerst)**
1. Leerzeile unter den Drop-Slots weg (vor dem Befüllen; vermutlich der Platz, an dem nach dem Befüllen der Bild-Tag erscheint).
2. Überflüssige Leerzeile nach „Advanced“ weg.
3. Chevron bei „Advanced“ steht zu weit rechts.
4. „Extra LoRAs (style, detail ...)“ umbenennen in „Custom LoRAs:“, den „+ Add“-Knopf ganz nach rechts, die Leerzeile danach löschen.
5. Text „PhotoCraft“ ganz unten links weg (der User fragt, was er bringt).
6. ComfyUI-Punkt unten: rot, wenn nicht verbunden, grün, wenn verbunden.
7. Slider: der dunklere Teil der Spur in PhotoCrafts Farbe `#686868`.
8. Slider überall rechts, gleich breit und fest; auch bei den modellspezifischen LoRAs rechts neben dem Text (heute: Workflow-LoRA-Slider unter dem Haken).
9. Slider-Werte müssen eintippbar sein (alle Slider).
10. „Sharpen result“, „Match colours“, „Edge feather“ und das Dropdown „Layer mask“ kommen unter „Advanced“; „Advanced“ heißt neu „Advanced settings“.

**B. Wichtig**
11. Startposition: Das Plugin wird nach dem PhotoCraft-Start oft zu weit links oben gesetzt; Drag and Drop nach unten macht dann Probleme (das Fenster verschwindet kurz). Es soll an einer festen Position starten.
12. Flux 2 Klein 9B: keine öffentliche Quelle mehr. Die vom User genannte Datei (`obsxrver/ComfyUI-Native-INT8_ConvRot`, `flux-2-klein-base-9b-int8-ConvRot.safetensors`) wurde am 27.10. geprüft: **nicht bytegleich** (anderer Inhalt, wohl das Base-Modell); Umbenennen geht nicht. Entscheidung des Users offen (siehe Handoff 6.B).

**C. Neue Funktionen**
13. Settings (Zahnrad): neben jeder Modell-Datei ein Knopf, mit dem der User sie gegen eine eigene Datei tauscht. Wortlaut vorschlagen (z. B. „Use my own file…“).
14. Strg+Z / Strg+Y: Die Notiz des Users ist abgebrochen („hier war gemeint, dass man mit STRG“) → beim User nachfragen, was gemeint war (bisher: Handoff-Aufgabe 6.8 alt).

**D. Recherche und Entscheidungen**
15. UX-Frage: Funktionen zuerst wählen, das Modell darunter (statt Modell-Tabs oben)? Folgen für die UX aufschreiben, Optionen nennen, nichts bauen.
16. State-of-the-art-UI-Fonts recherchieren, drei vorschlagen (Lizenz, Windows-Verfügbarkeit, Tk-Tauglichkeit).

**E. Danach laut Plan** (offen aus der alten Liste): Refresh/Reset (alt 6.7), Krea-2-Expand (alt 6.10), Flux-3-Expand-Steps (alt 6.11), Masken-Option A und Seam-Korrektur T2 (alt 6.12), restliche Design-Vorschläge (alt 6.3), dann L3, L4, Easy Mode.
