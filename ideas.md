# Todo: Ideen aus OpenFill (Recherche 2026-10-26)
Eingeplant in `PLAN.md`, Abschnitt 3 (T4 = Punkt 14, Geparkt = „Geparkt“). Diese Datei bleibt die Detailbeschreibung der offenen Ideen.
Quelle: github.com/beckettharriman/openfill (Apache-2.0, nur Doku gelesen, kein Code).
Regel: an Entscheidungen Optionen nennen, nicht still wählen. Ein Commit je Änderung, nie pushen.

## Erledigt (Verlauf in `docs/erledigt.md`, alte Fassung `docs/archiv/ideas-2026-10-29.md`)
- T1 PhotoCraft-Befehle prüfen: erledigt 27.10. (`docs/photocraft-befehle.md`).
- T2 Seam-Korrektur: gebaut 28.10., je Modell entschieden 29.10. (Fibo immer, Flux nie, Qwen mit Haken).
- T3a Live-Vorschau: gebaut 29.10. (Punkt 12); offen nur der Live-Test und das A/B grobe Farben gegen TAESD.
- T3b Verlauf der letzten 20 Läufe: gebaut 30.10. (Punkt 13; Uhr im Header, alles mit neuem Seed, LLM-Text mit Enhance aus). Der alte Text steht unten noch als Beschreibung.

## T3b Verlauf der letzten 20 Läufe, Lauf erneut laden (gebaut 30.10.)
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