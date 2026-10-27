# UI-Schriften (PLAN D.16)

**Entscheidung des Users 27.10.: Option A, Inter.** Gebaut: Kopie der Windows-Dateien (Inter 3.019, offizieller Build, Regular und SemiBold, zusammen ca. 630 KB) in `pccomfy/assets/fonts/` mit `OFL-Inter.txt`; Laden in `pccomfy/fonts.py`; eine Stufe kleiner (gemessen: „Multi Image Edit“ 85 statt 87 px bei 9 pt, Zeilenhöhe 15 statt 17 px bei 10 pt); Fett = SemiBold. `PCCOMFY_NO_INTER=1` zeigt zum Vergleich Segoe UI.

Stand 2026-10-27. Vergleichsblatt: `docs/ui-schriften.png` (mit Tk gezeichnet, so wie das Plugin Text darstellt, auf `PANEL` `#282828`, 9 und 10 pt). Heute: `FONT = "Segoe UI"` (gui_common.py), Größen 9, 10 und 11 pt.

## Befund

- **PhotoCraft benutzt Inter.** In `photocraft.exe` (0.15.1) stecken `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf` und `family":"Inter`. Eine Schrift mit PhotoCraft wäre der stärkste Grund für einen Wechsel.
- Auf dem Rechner des Users ist Inter zusätzlich in Windows installiert (von einer anderen Anwendung). Bei anderen Nutzern ist das nicht sicher: Für den Release müsste das Plugin sie mitliefern.
- Inter läuft **etwa 8 % breiter** als Segoe UI bei gleicher Punktgröße (Vergleichsblatt). Im 380-px-Fenster heißt das: Chips und lange Slider-Texte werden früher gekürzt. Ausweg: Inter eine Stufe kleiner setzen (Tk nimmt auch Pixelgrößen, z. B. `-12`/`-13` statt 9/10 pt).
- Segoe UI ist für die Windows-Darstellung (GDI, ClearType) am stärksten gehintet. Tk zeichnet über GDI. Die Schärfe des Fensters zählt zu dem, was der User „perfekt“ nennt: Jeder Wechsel braucht seine Abnahme im echten Fenster bei 100 % und 150 %.

## Wie Tk eine mitgelieferte Schrift lädt

Tk kann keine Schriftdatei direkt öffnen. Unter Windows lädt `AddFontResourceExW(pfad, FR_PRIVATE, 0)` (gdi32, per ctypes) die Datei nur für den eigenen Prozess, ohne Installation und ohne Adminrechte. Das muss vor `tk.Tk()` passieren, danach steht die Familie in `tkinter.font.families()`. Ist sie nicht da, bleibt `Segoe UI` als Rückfall. Platz: `pccomfy/assets/fonts/` plus Lizenzdatei. Hier noch nicht ausprobiert, weil Inter beim User schon installiert ist und der Test so nichts beweisen würde.

## Drei Vorschläge (Empfehlung zuerst)

| | Schrift | Lizenz | Auf Windows da? | Mitliefern | Bild bei 9/10 pt |
|---|---|---|---|---|---|
| **A** | **Inter** (empfohlen) | SIL OFL 1.1 (mitlieferbar, Lizenztext beilegen) | nein (nur bei manchen Nutzern) | 3 Dateien, je ca. 310 KB (Regular, Medium, SemiBold) | gleiche Schrift wie PhotoCraft; breiter, Ziffern klar |
| **B** | **Segoe UI Variable Text** | Microsoft, nicht weitergebbar | Windows 11 ja, Windows 10 nein (Rückfall Segoe UI) | nichts | fast wie heute, etwas offener; die Windows-11-Systemschrift |
| **C** | **IBM Plex Sans** | SIL OFL 1.1 | nein | 3 Dateien, ähnliche Größe | eigener, technischer Charakter; hier nicht gezeichnet (nicht installiert) |
| (D) | Segoe UI bleibt | Microsoft | ja, überall | nichts | heute; am schärfsten unter GDI |

Geprüft und nicht vorgeschlagen: **Geist** (OFL, aber für Web und Retina gemacht, unter GDI schwächer gehintet; nicht installiert, nicht gezeichnet), **Noto Sans** (OFL, auf dem Rechner da, aber im Vergleich am breitesten und ohne Bezug zu PhotoCraft).

## Was ein Wechsel kosten würde (A oder C)

- `FONT` in gui_common.py, Laden per `AddFontResourceExW` beim Start, Rückfall auf Segoe UI; die Größen 9/10/11 einmal neu abstimmen (wegen der Breite).
- Prüfen im echten Fenster: Chips, Funktions-Buttons, gekürzte Slider-Texte, Wert-Kästchen, Zahnrad-Fenster, 100 % und 150 %.
- Release: Lizenzdatei mitliefern und in den Credits nennen.

## Offen, den User fragen

1. Welche Option (A, B, C oder D)?
2. Bei A: gleiche Punktgrößen (breiter) oder eine Stufe kleiner?
3. Bei C: IBM Plex erst zum Ansehen laden (Download ca. 1 MB von Google Fonts/GitHub, nur mit Erlaubnis)?
