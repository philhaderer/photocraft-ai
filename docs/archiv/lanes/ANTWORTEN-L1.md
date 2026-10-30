# Antworten an Lane L1 (vom Haupt-Chat, Stand 2026-10-26 17:50)

## Wichtig zuerst: Branch aktualisieren
Der Haupt-Chat hat L1 und L2 in `next` zusammengeführt (dort sind auch deine Arbeit und die von L2). In deinem Ordner gibt es jetzt einen Branch `next`. Committe deinen Stand, dann: `git merge next` (in deinen Branch). Konflikte sind unwahrscheinlich; `FRAGEN.md` wird dabei aus dem Repo entfernt: sie bleibt künftig nur lokal (steht jetzt in .git/info/exclude, ebenso ANTWORTEN.md). Im Manifest habe ich den Eintrag "reference" von Qwen gestrichen (L2 hat den Modus aus den Tabs genommen). Es kommt ein neuer Modus `multi_edit` („Multi Image Edit“, ersetzt „Insert reference image“, nur Modelle mit Edit: Qwen, Fibo, Flux 2, Flux 3). Sein Manifest-Eintrag ist gleich dem von "edit" des jeweiligen Tabs; den trägt der Haupt-Chat beim Zusammenführen nach, du musst ihn nicht anlegen.

## Deine fünf Fragen
1. **A**, mit Ergänzung: Das Einstellungs-Fenster soll sich GENAUSO verhalten wie das Plugin-Fenster. Heute bleibt es sichtbar, wenn der Nutzer PhotoCraft schließt. Es soll wie das Hauptfenster an PhotoCraft hängen (winlink, „owned window“): mit PhotoCraft minimiert, versteckt und geschlossen werden.
2. **A**.
3. **A**. Die Änderung in der fremden Datei machst du NICHT. Schreib in `docs/entscheidungen-L1.md` genau auf, welche Datei, Methode und welche Zeilen sich ändern sollen. Der Haupt-Chat setzt es beim Zusammenführen um.
4. **A**.
5. **A**. (Info: Ziehen und Ablegen hat auf dem PC des Nutzers geklappt, L2 baut tkinterdnd2 ein. Sobald das gemerged ist, sagt dir der Haupt-Chat Bescheid, dann kannst du die yaml-Ablage im Einstellungs-Fenster ergänzen.)

## Neue Aufgaben aus dem Live-Test (bitte in dieser Reihenfolge)
Du darfst dafür `gui.py` (nur `_build`, Footer und Tab-Zeile), `gui_theme.py` und `gui_common.py` (Farben) ändern. Halte die Eingriffe klein und nenne sie in `docs/entscheidungen-L1.md`.

**A. Zahnrad unten rechts.** Nicht mehr neben den Tabs, sondern im Fußbereich ganz rechts (die Zeile mit „PhotoCraft ● ComfyUI ● [Refresh]“).

**B. Leerer Startzustand.**
- Beim ersten Start nach der Installation, wenn KEIN Modell verlinkt/gefunden ist: Das Fenster zeigt keinen einzigen Parameter, nur den Hinweis **„Link your model in the settings“** (und das Zahnrad).
- Auch wenn Modelle vorhanden sind: **Beim Start ist kein Modell gewählt.** Solange kein Tab gewählt ist, sind keine Parameter sichtbar (Prompt, Slider, Modi, Generate usw.). Erst der Klick auf einen Tab zeigt die Parameter dieses Modells. Der zuletzt benutzte Tab wird nicht wiederhergestellt.
- Was in diesem Zustand stattdessen steht („Choose a model“ o. ä.) und ob die Reset-/Generate-Zeile ganz weg ist: schlage mir 2 bis 3 Optionen in FRAGEN.md vor, bevor du das baust. Die übrige Arbeit machst du bis dahin.

**C. Die drei Zustände der Tab-Knöpfe.**
- **inaktiv:** Hintergrund `#282828`. Gemeint ist: die Farbe, die ein inaktiver Tab heute hat, soll im ganzen Plugin (überall, wo diese Farbe vorkommt) auf `#282828` geändert werden. Stelle fest, welche Konstante das ist (vermutlich PANEL `#404040`) und wo sie sonst vorkommt (Felder, Kästen, Dropdowns), und ändere sie zentral. Schreibe in die Entscheidungen, was sich dadurch alles mitändert und ob irgendwo der Kontrast schlecht wird (graue Schrift DISABLED, Griffe, Haken).
- **aktiv:** wie jetzt.
- **nicht verfügbar:** rote Schrift (Hintergrund wie inaktiv, `#282828`). Rot gut lesbar auf `#282828` wählen, nicht `#e5484d` blind übernehmen; nenne den Wert.
- Das bisherige „graue Tab“-Aussehen entfällt. Klick auf einen nicht verfügbaren Tab: wie in 2A (Einstellungen öffnen sich bei diesem Modell). Tooltip bleibt.

Bitte jeweils mit Tests (`python tests/run_all.py` grün) und einem Commit je Aufgabe (A, B, C). Was nur live prüfbar ist, benennst du.

---
## Nachtrag (17:55), ersetzt/ergänzt die Punkte B und C oben

**C, Hintergrundfarbe (bestätigt, präzisiert):** Die Farbe, die ein inaktiver Modell-Tab heute hat, wird überall dort `#282828`, wo genau dieser Farbton im Plugin vorkommt, also auch im Hintergrund von Drop-Picture-Slot, Seed-Feld, Refresh-Knopf, Eingabefeldern usw. Ändere die Konstante zentral (nicht einzeln pro Widget) und prüfe per Suche, ob dieser Farbwert auch als Text eingetragen ist (dann mitziehen). Andere Grautöne (Hauptfenster-Hintergrund, Linien, Griffe) bleiben unverändert. Liste in den Entscheidungen auf, wo die Farbe überall wirkt.

**B, Startzustand (geändert):** Nur beim ALLERERSTEN Start ist kein Modell gewählt. Sobald der Nutzer einmal ein Modell gewählt hat, bleibt beim nächsten Start **das zuletzt gewählte Modell** gewählt (und sein zuletzt gewählter Modus, falls das schon so gespeichert wird). Der Zustand „kein Modell gewählt, keine Parameter sichtbar“ gilt also: (1) beim ersten Start nach der Installation, (2) wenn gar keine Modelle verlinkt sind („Link your model in the settings“), (3) wenn das zuletzt gewählte Modell inzwischen nicht mehr verfügbar ist (Dateien fehlen): dann kein Tab gewählt, statt eines kaputten Tabs. Speichere das letzte Modell dort, wo du die anderen Einstellungen ablegst, und sag in den Entscheidungen, wo. Die Optionen für den Hinweistext im Zustand „kein Modell gewählt, aber Modelle vorhanden“ legst du mir wie angekündigt in FRAGEN.md vor.

---
## Runde 2 (18:30), Antworten auf deine FRAGEN.md
1. **A**  2. **A**  3. **A** (Titelleiste bleibt `#404040`)  4. **A**.
Bitte den Startzustand-Teil von Aufgabe B damit fertig bauen (Tests grün, ein Commit), dann sag mir Bescheid, dass du fertig bist.
