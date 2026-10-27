# Todo: Ideen aus OpenFill (Recherche 2026-10-26, nichts gebaut)
Eingeplant in `PLAN.md`, Abschnitt 3 (T1 = Punkt 6, T2 = Punkt 9, T3a/T3b/T4 = Punkte 12 bis 14, Geparkt = „Geparkt“). Diese Datei bleibt die Detailbeschreibung.
Quelle: github.com/beckettharriman/openfill (Apache-2.0, nur Doku gelesen, kein Code).
Regel: an Entscheidungen Optionen nennen, nicht still wählen. Ein Commit je Änderung, nie pushen.

## T1 PhotoCraft-Befehle prüfen (beschlossen)
Ziel: Tabelle "Befehl → existiert in PhotoCraft 0.15.1? → Folge für uns". OpenFill nennt (getestet 0.12–0.16):
- select.modify.feather, select.modify.expand → Live-Feather-Vorschau (offener Befund 4: Befehlsname)
- select.saveSelection / select.loadSelection, layer.layerMask.revealSelection
- layer.new.group (Gruppe für Variants)
- history.newSnapshot / history.selectSnapshot (mehrere Schritte = ein Undo), history.deleteState
- image.crop mit Rechteck über den Canvasrand hinaus (offener Befund 3: Crop übernehmen), channel.duplicate, layer.copyToDocument
Vorgehen: zuerst im Bridge-Code nachsehen, was wir schon nutzen (grep in pccomfy); der Rest gegen die laufende PhotoCraft-Instanz prüfen. Ergebnis als kurze Tabelle liefern.
Abnahme: jede Zeile ja/nein, mit Folge (z. B. "Feather-Vorschau möglich mit Befehl X").

## T2 Seam-Korrektur (Tonangleich) als A/B-Test (beschlossen: testen)
Hintergrund: Befund 1 (hellerer Rechteckrand beim Sky-Test, verschobene Kante beim Pool-Test). OpenFill `seam_correction`: misst die Abweichung der Generierung dort, wo sie zum Original passen muss, und gleicht sie über die Ebene aus; Detail bleibt unberührt. Beispielwerte laut OpenFill: 5 Stufen Sprung am Rand, ca. 8 am alten Expand-Rand. Dazu: Ebenenmaske wächst nur um den Feather-Radius, ist über der Auswahl deckend. Beweisdaten im Repo: docs/evidence/seam-2026-10-16/.
Erwartung (ehrlich): korrigiert Tonunterschiede (Sky-Test). Eine geometrische Verschiebung (Pool-Test) korrigiert das nicht, dafür bräuchte es Registrierung (Phasenkorrelation), separate Entscheidung.
Test muss den Unterschied zum Jetztstand deutlich zeigen. Optionen:
 A) Ein Lauf liefert zwei Ebenen, "roh" und "korrigiert" (gleicher Seed, Namenssuffix), Nutzer schaltet die Sichtbarkeit um. Empfohlen: kein zweiter Lauf, direkter Vergleich.
 B) Schalter Ein/Aus, zwei Läufe mit gleichem Seed (teurer, bei Turbo-Modellen seedabhängig).
 C) Zusätzlich Messwert in der Statuszeile (Kantensprung in Stufen vorher/nachher).
Testfälle: Sky-Test, Pool-Test, jeweils Layer mask "soft" und "none"; Fibo, Qwen, Flux 2/3.
Abnahme: Nutzer sieht im A/B klar, ob der Rand verschwindet; Schalter standardmäßig aus, bis bestätigt.

## T3a Live-Vorschau unten im Plugin (beschlossen)
- ComfyUI braucht --preview-method taesd (Nutzer hat TAESD-Dateien). Bridge liest die Startargumente aus /system_stats und zeigt einen Hinweis, wenn es fehlt.
- Vorschau-Frames kommen als binäre Websocket-Nachrichten (Bridge nutzt den Websocket schon); Anzeige per Pillow im Tk-Fenster, Breite max. 380.
- Zu prüfen: welche TAESD-Datei gehört zu welchem unserer 5 Modelle (Qwen 2.1, Flux 2, Flux 3, Fibo, MOSS, Krea); ohne passende Datei fällt ComfyUI auf eine grobe Farbnäherung zurück (comfy/latent_formats.py, latent_preview).
- Keine Vorschau in der LLM-Phase und der SeedVR2-Stufe; bei Turbo (4–8 Schritte) nur wenige Frames.
Optionen Layout: (a) Platz immer reserviert, (b) Bereich nur während des Laufs sichtbar (Fensterhöhe folgt dem Inhalt), (c) Klick vergrößert.
Abnahme: Nutzer testet live, Vorschau läuft pro Modell, Fenster bei 380 px nicht abgeschnitten.

## T3b Verlauf der letzten 20 Läufe, Lauf erneut laden (beschlossen)
Basis: data/exchange/runs.jsonl hat schon Funktion, Workflow, Seed, Größe, Prompt. Erweitern um Tab, Negativ-Prompt, Schalter, Regler, LLM-Haken.
Entscheidungen (Optionen nennen):
 - Wo: Dropdown neben Reset / kleines Popup / Liste unter dem Prompt.
 - Was laden: nur Prompt, oder alle Einstellungen eines Laufs; Seed fest oder neu.
 - Den vom LLM geschriebenen Text mitspeichern, damit man ihn ohne LLM wiederverwenden kann?
 - Verknüpfung mit dem Ebenennamen (Presetname + laufende Nr.)?
Laden startet nichts automatisch, wechselt bei Bedarf Tab und Funktion. Nicht live prüfbar in der VM (kein Tk).
Nicht anfassen: Cancel, Undo, Shift+Enter (neue Zeile), Strg+Enter (Run) bleiben wie sie sind.

## T4 Modell-Manager von OpenFill mit unserem Stand vergleichen (Nutzer lädt das Repo)
Ziel: Bericht "was macht er besser, was davon brauchen wir". Ohne Code nur Doku gelesen, das ist zu prüfen.
Dateien (laut Doku, Namen im Repo prüfen): gimp-openfill/openfill/catalog.py (rank_score, parse_live_entries), hub.py, hardware.py (fit), models/catalog.json (Felder: Größe, sha256, Lizenz, gated, gepinnte Custom-Node-Commits), models/comfy_setup.json, Supervisor/Task-Worker (Download mit Range-Resume, .part, sha256, atomares Umbenennen), docs/security.md (HF-Token nur an huggingface.co, nicht bei Redirects, aus Logs entfernt, config.json), docs/design.md, docs/performance.md, backend.describe_error / ui_text.py (Fehlertexte mit nächstem Schritt).
Prüffragen:
 1. Wie wird die Hardware-Prüfung gemacht und liefert sie 4 Stufen (passt / langsamer / zu groß / unbekannt)? Als Vorlage für unseren Statuspunkt (Shipping-Dokument Abschnitt 6) geeignet?
 2. SHA-256: wofür bei uns nötig (nur Download-Prüfung? umbenannte Dateien erkennen?) Alternative Dateigröße + Header-Hash.
 3. HF-Token: nötig nur für gated Dateien; Alternative "Seite öffnen"-Knopf. Wo wird das Token gespeichert, auch unter Windows?
 4. Brauchen wir überhaupt einen Downloader (Shipping-Addendum Option 3) oder reicht Preflight + Link?
 5. Welche Funktionen daraus passen zu Shipping-Dokument Abschnitt 5 (inventory, resolve, check_workflow, preflight)?
Abnahme: kurze Gegenüberstellung OpenFill ↔ unser Stand, mit Empfehlung (übernehmen / anpassen / weglassen).

## Geparkt (vom Nutzer nicht entschieden)
- Expand: Warnung über 25 % Wachstum pro Seite, automatische Runden, bei einseitigem Expand nur lokales Kontextband (Befund 2).
- Schnelles Remove mit LaMa in voller Auflösung (comfyui-inpaint-nodes ist GPL-3.0: nur als Abhängigkeit, nicht kopieren).
- ComfyUI automatisch starten/beenden und herunterladen (nur für andere Nutzer).
- Gerät beim Start loggen / CPU-Warnung, Open log folder (nur für andere Nutzer, Release).
Verworfen: Varianten-Picker (jedes Ergebnis ist eine Ebene), Cancel/Undo neu bauen.