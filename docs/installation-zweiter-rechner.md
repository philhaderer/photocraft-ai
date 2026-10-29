# Installation auf einem zweiten Rechner (Stand 29.10.2026)

Das Plugin liegt privat auf GitHub: <https://github.com/philhaderer/photocraft-ai> (Account `philhaderer`, Branch `main`; nur du siehst es). Hochgeladen und aktualisiert wird vom Hauptrechner aus; auf dem zweiten Rechner wird nur geholt.

## Was der zweite Rechner braucht

| Teil | Version | Woher |
|---|---|---|
| Windows | 10 oder 11, NVIDIA-Grafikkarte mit 16 GB | |
| GitHub Desktop | aktuell | <https://desktop.github.com> |
| Python | 3.11 oder neuer mit „tcl/tk“ (hier: 3.12.9) | <https://www.python.org/downloads/windows/> |
| PhotoCraft | 0.17.0 portable | den Ordner `C:\programs\photocraft-0.17.0-windows-x64-portable` vom Hauptrechner kopieren (oder neu herunterladen) |
| ComfyUI | 0.42.0 oder neuer (hier: ComfyUI-Easy-Install Cuda13) | wie auf dem Hauptrechner |
| ComfyUI-AusBoss | 2.13.0 oder neuer | ComfyUI-Manager oder <https://github.com/ausboss/ComfyUI-AusBoss> (nur für Upscale/Refine) |
| Modelle | die Dateien der Modelle, die du nutzen willst | Zahnrad-Fenster des Plugins (Downloadlinks) oder vom Hauptrechner kopieren |

Alle übrigen Knoten der Workflows sind in ComfyUI selbst enthalten.

## Schritte

1. **GitHub Desktop** installieren und starten, mit dem Account `philhaderer` anmelden („Sign in to GitHub.com“).
2. **Repo holen:** „File › Clone repository…“, Reiter „GitHub.com“, `philhaderer/photocraft-ai` wählen. „Local path“ z. B. `C:\programs\photocraft-ai`. „Clone“.
3. **Python** installieren (Haken bei „tcl/tk and IDLE“ und „Add python.exe to PATH“ gesetzt lassen).
4. Im Plugin-Ordner **`setup-windows.bat`** doppelklicken. Es legt `.venv` an, installiert Pillow, NumPy, websocket-client und tkinterdnd2 und schreibt `data\python.txt`. Am Ende steht „Setup done“.
5. **PhotoCraft 0.17** nach `C:\programs\photocraft-0.17.0-windows-x64-portable` kopieren (ein anderer Ort geht auch, dann in Schritt 7 den Pfad anpassen).
6. **ComfyUI** einrichten und starten, AusBoss installieren, die Modelle ablegen. Liegen die Modelle wie auf dem Hauptrechner außerhalb von ComfyUI (`C:\AI_Models`, `D:\AI_Models\Lora`), braucht ComfyUI dieselbe `extra_model_paths.yaml`; am einfachsten vom Hauptrechner kopieren und die Laufwerke prüfen.
7. **Desktop-Verknüpfung** anlegen: im Plugin-Ordner in die Adresszeile des Explorers `powershell` tippen, Enter, dann:

   ```
   .venv\Scripts\python.exe -m pccomfy shortcut --photocraft "C:\programs\photocraft-0.17.0-windows-x64-portable\photocraft.exe"
   ```

   Auf dem Desktop liegt jetzt „PhotoCraft AI“ mit dem PhotoCraft-Symbol.
8. **Erster Start:** ComfyUI läuft, PhotoCraft ist zu. Doppelklick auf „PhotoCraft AI“: PhotoCraft startet, nach ein paar Sekunden erscheint das Plugin. Im Zahnrad-Fenster („Models“) zeigt rot, welche Modelldateien fehlen, mit Downloadlink und Größe.

## Später aktualisieren

GitHub Desktop öffnen, oben „Fetch origin“, dann „Pull origin“. Danach das Plugin neu starten. Auf dem zweiten Rechner nichts committen oder hochladen; Änderungen entstehen auf dem Hauptrechner (sonst gibt es zwei Stände, die zusammengeführt werden müssen).

## Was nicht im Repo ist

- `data\` (Einstellungen, zuletzt benutzte Werte, Laufnummern, Token, Testbilder): wird auf dem zweiten Rechner neu angelegt. Eigene Modell-Zuordnungen („Choose another file…“) und Favoriten stehen in `data\settings.json`; wer sie mitnehmen will, kopiert die Datei.
- Die Modelle (viele GB) und ComfyUI selbst.
- Deine Starter `photocraft-ai 0.16.bat` und `0.17.bat` (die Verknüpfung ersetzt sie). `photocraft-ai.bat` im Repo zeigt noch auf PhotoCraft 0.14.0.
