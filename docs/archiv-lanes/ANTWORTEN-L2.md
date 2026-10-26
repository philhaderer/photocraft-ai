# Antworten an Lane L2 (vom Haupt-Chat, Stand 2026-10-26 17:50)

## Wichtig zuerst: Branch aktualisieren
Der Haupt-Chat hat L1 und L2 in `next` zusammengeführt. In deinem Ordner gibt es jetzt einen Branch `next`. Committe deinen Stand, dann: `git merge next` (in deinen Branch). Beim Zusammenführen gab es zwei Konflikte, die ich gelöst habe: Die Klassenzeile in gui.py lautet jetzt `class App(SettingsMixin, RefSlotsMixin, ThemeMixin, ...)`, und `tests/test_phase0.py` prüft beides. `FRAGEN.md`/`ANTWORTEN.md` bleiben nur lokal (in .git/info/exclude eingetragen).

## Das Missverständnis, bitte zuerst lesen (Briefing des Nutzers)
- **„Insert reference image“ wird durch „Multi Image Edit“ ERSETZT.** Das ist ein eigener MODUS in der Moduszeile an der Stelle, wo „Insert reference image“ stand. Er heißt im Fenster **„Multi Image Edit“** (Schlüssel `multi_edit`).
- **Nur Modelle mit Edit-Fähigkeit** haben diesen Modus: Qwen, Fibo, Flux 2, Flux 3.
- **Die Slots erscheinen NUR in diesem Modus**, nicht bei Edit, Fill oder Expand. (Das ist auch die Antwort auf deine Frage 4: „Nur bei dem neuen Modus“.)
- Der alte Modus „Reference“ samt Radiobutton „Insert reference image“, dem grauen Knopf und den Feldern `ref_style`/`ref_collage`/`ref_cutout` entfällt jetzt vollständig. Du darfst dafür `gui_common.py` (MODE_LABELS), `gui_modes.py`, `gui_state.py` und die alten Teile in `bridge.py`/`gui.py` ändern. Alte Presets mit dem Modus dürfen nicht abstürzen (fallen auf den ersten Modus zurück).
- Welcher Workflow läuft im neuen Modus, ob die Auswahl (Selektion/Maske) benutzt wird und wie das Ergebnis platziert wird: schlage mir Optionen in FRAGEN.md vor, bevor du das baust (Vorschlag: die Edit-Workflows des jeweiligen Modells, Ganzbild-Edit, keine Maske). Den Manifest-Eintrag für `multi_edit` (L1) trägt der Haupt-Chat nach, er gleicht dem von „edit“.

## Deine Antworten
1. **A, klappt.** Baue tkinterdnd2 fest ein (setup-windows.bat, README-WINDOWS.md, Hinweis, wenn es fehlt, ohne Absturz). Das Test-Skript war erfolgreich.
2. Siehe oben: „Insert reference image“ wird ersetzt, Knopf und alter Modus werden entfernt.
3. **Grau** zum Testen (ein einziger Wert an einer Stelle, später evtl. transparent oder weiß).
4. Siehe oben: nur im Modus „Multi Image Edit“.
5. **B, mit Änderungen:**
   - Der Beschreibungstext soll **kürzer** werden (ein knapper Satz; sag mir den gewählten Prompt für Qwen 3.5 9B).
   - Er wird wie jetzt **unter dem Bild** angezeigt UND **hinten an den Prompt angehängt**. Den Knopf „Descriptions to prompt“ brauchst du dann nicht mehr.
   - Zum Testen: **je Slot mit Beschreibung ein Knopf „Text kopieren“** (Icon).
   - **Wichtig:** Der Nutzer will verstehen und testen, **wie der Gesamtprompt zusammengesetzt wird, für jedes Modell** (Qwen, Fibo, Flux 2, Flux 3): Bildnamen/Tags + Beschreibungen + sein Text. Lege `docs/prompt-aufbau.md` an: je Modell ein Beispiel des echten Gesamtprompts, erzeugt über die echte Funktion (kein Handtext), und einen Test, der die vier Beispiele ausgibt. Wo sieht der Nutzer den gesendeten Prompt im Betrieb? (`data/exchange/runs.jsonl` hat ihn schon; sag, ob das reicht.)
6. **Icons statt Text, klein, am rechten Rand jedes Slots.** Für Einfügen, Datei hinzufügen, Freistellen, Stift, Beschreiben, Text kopieren, Entfernen. Zeichne sie wie die vorhandenen Icons (`icon_image` in gui_common, keine neuen Bilddateien). Jedes Icon bekommt einen kurzen Tooltip mit dem bisherigen Wort („Pen“, „Cut out“ …). Die Icons liegen als schmale Leiste am rechten Rand INNERHALB des Slots, damit die Slots weiter ins 380-px-Fenster passen. Schreibe, wie viele Slots je Modell hineinpassen und wie die Leiste aussieht, in `docs/entscheidungen-L2.md`.

Reihenfolge: (1) Modus „Multi Image Edit“ ersetzt „Insert reference image“, (2) Icons, (3) Beschreibung + Prompt-Aufbau + tkinterdnd2. Je Aufgabe ein Commit, Tests grün, benenne, was nur live prüfbar ist. Offene Fragen wie gehabt in FRAGEN.md.

---
## Runde 2 (18:30), Antwort auf Frage 7 und Klarstellung
**7 = A**, aber mit einer Klarstellung, weil das Konzept offenbar nicht klar war:
- Die Referenz-Slots im Plugin sind **zusätzliche Bilder, die in den Workflow mitgeschickt werden, und zwar in dessen offene Image-Eingänge.** Technisch einfach: den LoadImage-Knoten kopieren, der Slot füllt diesen Knoten.
- Reihenfolge: **Das offene Bild in PhotoCraft ist Bild 1 im Workflow, Slot 1 im Plugin ist Bild 2, Slot 2 ist Bild 3 usw.**
- Eine Auswahl/Markierung am Hauptbild wird ignoriert (A). Der Nutzer bezweifelt, dass das mit Markierungen funktioniert.
- Das hast du im Kern schon so gebaut. Bitte prüfe und melde in `docs/entscheidungen-L2.md` und in FRAGEN.md, falls etwas davon NICHT stimmt: (a) Hat **jeder** der vier Workflows (Qwen, Fibo, Flux 2, Flux 3) offene Image-Eingänge für so viele Slots, wie das Modell zulässt? Liste je Workflow: wie viele Eingänge, welcher Knoten, und was passiert bei leerem Slot. (b) Entspricht die Nummerierung (Slot n = Bild n+1) genau dem, was in den Prompt-Tags steht?
- **Wie man Multi Image Edit ideal promptet, ist offen.** Der Nutzer testet das zuerst von Hand in ComfyUI und fragt bei Misserfolg nach. Baue keine automatische Prompt-Verfeinerung auf Verdacht. `docs/prompt-aufbau.md` bleibt die Beschreibung des heutigen Stands.

## Recherche zur Flux-3-BBox-Erweiterung (Haupt-Chat; bitte nur lesen, nichts bauen)
Quelle: github.com/MoistRecognition69/f3k-bbox-nodes1.0 und die ComfyUI-Doku. Was wirklich dort steht:
- Das Paket bringt **nur die Zeichenfläche** (Knoten „Create Bounding Boxes (Nodes 1.0)“) für ComfyUIs alte Oberfläche. Der Kern-Knoten „Create Bounding Boxes“ kann das nur in der neuen Oberfläche (Nodes 2.0). Ausgabe `elements`: je Box Typ (obj/text), Box `[ymin,xmin,ymax,xmax]` auf einer Skala 0 bis 1000, Beschreibung, optional Text und Farben.
- Der eigentliche Knoten **„FLUX 3 Image Layout Prompt“** ist ein **ComfyUI-Kernknoten**, kein Teil des Pakets. Er hängt eine Layout-Tabelle an den Prompt; im Prompt verweist man mit `<obj_N>` auf Box N. Ohne Boxen bleibt der Prompt unverändert. Farbpaletten werden ignoriert (Farben in die Beschreibung).
- **Aber:** Beide Seiten sprechen vom **„FLUX 3 Image“-Knoten, einem Partner-Knoten (Cloud-API, Credits)**. Ob das lokale **Flux 3 Klein** diese Layout-Tabelle versteht, steht nirgends. Die Doku sagt auch **nichts darüber, Referenzbilder per Box zu platzieren**. Beschrieben wird nur Layout über Text und Beschreibung je Box. Der Nutzer hat vermutet, dass man damit Referenzbilder platzieren kann: das ist NICHT belegt und müsste getestet werden.
- Die Doku zum API-Knoten: bis zu 10 Referenzbilder, im Prompt als `image 1`, `image 2` usw. angesprochen. Das gilt für den Cloud-Knoten. Dein Tag-Muster für lokales Flux 3 Klein (`<ref_image_{i}>`) ist eine eigene Annahme und weiter ungetestet; bitte so kennzeichnen.
- Für das Plugin braucht man das Zeichen-Paket vermutlich gar nicht: das Plugin hat die PhotoCraft-Auswahl (ein Rechteck ist eine Box) oder könnte selbst Boxen zeichnen. Das ist eine spätere Entscheidung, noch nicht jetzt.
Der Nutzer testet Flux 3 Klein mit Layout-Prompt zuerst von Hand. Bis dahin: nichts bauen, nur in `docs/entscheidungen-L2.md` unter „offen“ vermerken.

Danach weiter wie besprochen. Wenn du fertig bist, sag Bescheid.

---
## Runde 3 (2026-10-26 19:20), Testergebnisse des Nutzers und Entscheidungen
Zuerst: `git merge next` (Haupt-Chat hat danach noch `docs/flux3-bbox-workflow-notes.md` ergänzt). Lies diese Datei dazu. Dein Stand wurde live getestet.

### Funktioniert (nicht anfassen)
- Cut out (Freistellen): "funktioniert super".
- Drag and Drop: "funktioniert super".
- Referenzieren nach dem Muster "the woman in <image2> is sitting on a beach" auf einer leeren (weißen) Fläche funktioniert.

### Änderungen an den Slots (der Reihe nach)
1. **Icons in den Slots 70 % größer** (Faktor 1,7; ein einziger Wert an einer Stelle).
2. **Pen-Symbol komplett streichen** (Icon, Funktion, Code, Tooltip, Tests, Doku). Auch die Pen-Logik in `prepare_image` o. ä. entfernen, falls sie nur dafür existiert.
3. **Image-Tag unter dem Slot zentriert** anzeigen.
4. **Hinweiszeile immer anzeigen**: "Max. images: x" (x = `max_refs` des Modells) statt "This model takes ...". Gleiche Schriftgröße und Farbe wie der Text "Name them in your text ...", **direkt anschließend** (kein Leerraum dazwischen). Die Lücke zwischen dieser Zeile und dem Negative Prompt vermeiden (kein leerer Platzhalter, wenn nichts angezeigt wird).
5. **Tags im Promptfeld beim Modellwechsel automatisch umschreiben** auf die Namensregel des neuen Modells (Qwen `<image{n}>`, Fibo `<image_{n}>`, Flux 2 `image {n}`, Flux 3 `<ref_image_{i}>`). Nur echte Tags erkennen (nicht beliebigen Text), Nummerierung dabei korrekt umrechnen (Flux 3: `ref_image_0` = Hauptbild, `ref_image_1` = Slot 1; bei den anderen Modellen ist Hauptbild = Bild 1, Slot 1 = Bild 2). Rückwärts und vorwärts muss verlustfrei sein. Test mit allen 4x4 Kombinationen.
6. **Tipp unter dem Promptfeld** im Modus Multi Image Edit, exakt: `You can start with a white image and use the reference images below to place them on the canvas.`

### Entscheidungen des Nutzers zu offenen Fragen
- **Qwen: mehr als 2 Slots (Entscheidung 1A, siehe Haupt-Chat).** Der Nutzer-Workflow "Qwen 2.1" hat 9 Bild-Eingänge. Prüfe, wie viele unser Qwen-Workflow tatsächlich zulässt, und nimm so viele, wie der Workflow sinnvoll trägt (8 Slots plus Hauptbild als Obergrenze). Die Slots erscheinen nach und nach (z. B. in Reihen zu 3, neuer Slot erst, wenn der letzte belegt ist), damit das 380-px-Fenster nicht überläuft. Wenn für 16 GB VRAM eine kleinere Zahl sicherer ist, nenne mir Zahl und Grund in FRAGEN.md; baue bis dahin die Obergrenze mit einer einzigen Konstante je Modell (`max_refs`).
- **Flux 3 Boxen (Entscheidung 2A):** Variante: Die PhotoCraft-Auswahl des Hauptbilds wird zur Box. Je Slot ein zusätzliches Icon "Auswahl als Ort verwenden" plus Beschreibung. **Bitte jetzt NOCH NICHT bauen.** Lies zuerst `docs/flux3-bbox-workflow-notes.md` und schreibe in FRAGEN.md einen kurzen Plan mit Optionen (insbesondere: lässt sich die Box per API in `CreateBoundingBoxes` einspeisen, oder baut das Plugin die Layout-Tabelle selbst; was bleibt zu testen). Ein echter Testlauf braucht die Erlaubnis des Nutzers (GPU), frag vorher.
- **Prompting-Guide (Entscheidung 3):** Erstelle `docs/prompting-multi-image.md` für Multi Image Edit, mit Schwerpunkt Flux 3 (Klein). Trenne klar: (a) belegte Aussagen der Hersteller/Doku, mit Quelle; (b) Handtests des Nutzers (z. B. "the woman in <image2> is sitting on a beach" auf weißer Fläche funktioniert); (c) offene Vermutungen. Keine automatische Prompt-Verfeinerung.
- **Easy Mode** ist nicht Teil von L2 und kommt zuletzt.

### Reihenfolge
(1) Punkte 1 bis 6 oben, ein Commit pro Punkt, Tests grün. (2) Qwen-Slots. (3) Prompting-Guide. (4) Plan für Flux-3-Boxen in FRAGEN.md. Entscheidungen weiter in `docs/entscheidungen-L2.md`. Nur live Prüfbares benennen. Wenn fertig: "fertig" melden.
