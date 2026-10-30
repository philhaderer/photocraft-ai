# Handoff: Technik für die nächste Sitzung (Stand 2026-10-30)

Zweck: wie man in diesem Repo arbeitet und prüft. Regeln und Arbeitsweise stehen in `CLAUDE.md`, offene Arbeit und Entscheidungen in `PLAN.md`, der Verlauf in `docs/erledigt.md`. Die alte, lange Fassung dieser Datei liegt in `docs/archiv/HANDOFF-2026-10-28.md`.

## 1. Repo und Git-Stand

- Pfad `C:\programs\photocraft-comfyui-bridge`, Fork von Peszemeszek/photocraft-comfyui-bridge.
- Branches: `main` (Upstream), `windows-fibo` (zuletzt abgenommener Stand), **`next`** (Integrationsstand, den der Nutzer testet). Alte, gemergte Arbeits-Branches wurden am 30.10. auf Wunsch des Users gelöscht; neue Branches nach dem Merge stehen lassen, bis er wieder aufräumen will.
- Remotes: `origin` = Upstream (nie pushen), `private` = <https://github.com/philhaderer/photocraft-ai> (nur auf Wunsch: `git push private next:main`).
- Tags: `backup-2026-10-26` (6df02df, vor Phase 0), `vor-claude-code` (65e955f).
- In PowerShell mehrzeilige Commit-Nachrichten mit `git commit -F <datei>` (Datei im Scratchpad).
- Tests: `python tests/run_all.py` (64 Dateien, alle grün, ca. 30 s). Python des Nutzers: Pfad in `data/python.txt`.
- Diagnose: `data/exchange/last-graph.json` (letzter Graph), `data/exchange/runs.jsonl` (eine Zeile je Lauf); ComfyUI-Historie über `http://127.0.0.1:8188/history`.

## 2. Umgebung

- ComfyUI: `C:\programs\ComfyUI-Easy-Install Cuda13\ComfyUI` (0.42.0), Modelle in `C:\AI_Models` (diffusion_models, clip, vae) und `D:\AI_Models\Lora`. RTX 4070 Ti Super (16 GB), 64 GB RAM.
- PhotoCraft: portable Ordner `C:\programs\photocraft-<version>-windows-x64-portable` für 0.14.0, 0.15.1, 0.16.0 und 0.17.0. 0.16 ist seit 28.10. die Hauptversion des Nutzers; die Desktop-Verknüpfung ist für 0.17 gedacht; Mask density braucht 0.17+. Alle haben `photocraft-cli.exe` (Befehlsliste per `photocraft-cli commands --json`, kopfloser Betrieb). `photocraft-ai.bat` zeigt noch auf 0.14.0.
- Sein Bildton: Fenster 380 px fest breit, Titelleiste `#404040`; Flächen `#282828` (`PANEL`), Fenstergrau `#535353` (`BG`), Akzent Orange `#f28c28`; Slider-Spur dunkel `#686868`.
- Python des Nutzers hat veraltete Zertifikate für Civitai (SSL-Fehler): Civitai-API per PowerShell `Invoke-RestMethod` abfragen; Hugging Face geht auch aus Python.

## 3. Prüfen ohne GPU und ohne sein PhotoCraft

- **Kopfloses PhotoCraft:** `photocraft-cli serve --port <p> --control-token-file <f> --automation-read-root <x> --automation-write-root <x>`, im Plugin `PhotoCraft(port=p, token_file=f, headless=True)`; dazu ein nachgemachtes ComfyUI (`tests/test_reference_mode.FakeComfy`). Einzelne Befehle: `photocraft-cli run --new …`.
- **Echtes Tk-Fenster versteckt:** `root.withdraw()`, eigenes `PCCOMFY_HOME` im Scratchpad, PhotoCraft-Port 1, ComfyUI-URL `http://127.0.0.1:1`; Modelle über `cb_workflow["values"]` wählbar machen.
- **Sein laufendes PhotoCraft** nur lesend abfragen (`session`, `document.inspect`).
- **Screenshot des echten Fensters** (nur, wenn der Nutzer es nicht selbst prüfen kann): Skript im Scratchpad setzt `PCCOMFY_HOME` auf einen Temp-Ordner, `gui.winlink.available = lambda: False`, baut `gui.App(cfgmod.load())`, wählt Funktion/Modell und macht nach **8 s** (`root.after(8000, …)`, sonst setzt das Start-Refresh das Modell zurück) mit `PIL.ImageGrab` den Screenshot. Die rote Meldung „Can't connect to PhotoCraft“ ist dabei normal.
- In der Bash-Shell keine langen Python-Heredocs mit typografischen Anführungszeichen: Skript mit dem Datei-Werkzeug ins Scratchpad schreiben.
- Echte Generierungen (GPU) nur mit Erlaubnis des Nutzers; die comfyui-Werkzeuge (Queue, History, Logs) gehen immer.

## 4. Wie das Ergebnis in PhotoCraft landet (Code-Karte)

- **Platzieren:** `Bridge._place_png` öffnet das PNG, `layer.copyToDocument` mit `offset`, aktiviert das PNG wieder und schließt es (die Kopie macht das Ziel aktiv). Ist oben eine Gruppe, wird das erste Ergebnis mit `layer.moveTo` darüber gesetzt. Alle Ergebnisse kommen ganz oben in den Stapel.
- **Masken:** hart über `layer.layerMask.revealSelection` (verbraucht die Auswahl, danach `select.reselect`); weich über eine Hilfsebene mit der Maske als Transparenz, `select.loadSelection {channel: "transparency"}`, `revealSelection`. Die Auswahl des Nutzers sichert `_keep_selection` in einem Kanal. Mask density über `layer.layerMask.edit` (0.17+).
- **Varianten-Gruppe:** `Bridge._group` (`layer.new.groupFromLayers`), Name aus `Request.group_name`.
- **Feather-Vorschau:** `Bridge.show_feather` / `hide_feather` (Quick Mask; Kanal `pccomfy-preview-<tag>`; das Dokument wird über Position UND Kanal gefunden, weil zwei Dokumente gleich heißen können). Gleiche Maske wie der Lauf: `bridge.soft_layer_mask`.
- **Fill-Maske:** `imaging.outer_feather` (innen voll, Rand außen, Breite = Edge feather); Remove nutzt `auto_feather`. Eine geglättete Auswahl (`imaging.is_soft`) bleibt, wie sie ist. Expand-Maske für Krea/MOSS: `imaging.outpaint_mask`.
- **Seam-Korrektur:** `imaging.seam_correct`, je Modell über `Model.seam`.
- **Layer mask:** `LAYER_MASKS` = soft, selection (hard), none; `layer_mask_key` macht aus altem „auto“ „soft“.

## 5. Befunde zum Weitergeben

- **Gleicher Seed, anderes Bild (Flux 2):** Edit schickt das sichtbare Dokument; nach Lauf 1 liegt dessen Ergebnis obenauf. Gegenprobe: generieren, Undo, gleicher Seed noch einmal.
- **Branches löschen** ändert nichts am Code: Ein Branch ist nur ein Namensschild; nach dem Merge steckt alles in `next`.
- **flux2-vae:** die Kopie in `Comfy-Org/Flux-2-Dev` ist bytegleich mit der des Nutzers; die in den Klein/MOSS/Fibo-Repos sind 2264 Byte kleiner (anderer Dateikopf) und laden genauso.
- **Fibo und glatte Auswahl:** Eine Ellipse oder ein Lasso mit Anti-Aliasing gilt als schon weich; der Edge-feather-Regler wirkt dann kaum. So gewollt.
- **Flux 2 Klein:** Andere Uploads derselben Datei sind nicht bytegleich (Einzelheiten im Archiv-Handoff, 6.B.12); nur die obsxrver-Datei ist geprüft.
