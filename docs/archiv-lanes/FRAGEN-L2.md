# Fragen an dich (Lane L2)

Antworte bitte in `ANTWORTEN.md` (Nummer und Buchstabe reichen, z. B. "1 A"). Ich mache inzwischen mit allem weiter, was nicht davon abhängt.

## 1. Drag and drop: darf ich die Zusatz-Software "tkinterdnd2" fest einbauen?
Drag and drop ist das Ziehen einer Bilddatei aus dem Explorer in einen Slot. Dafür braucht das Fenster ein kleines Zusatzpaket (tkinterdnd2). Ohne das Paket läuft alles andere (Strg+V, Paste, Add file), nur das Ziehen geht nicht, und das Fenster sagt es dann in einer Zeile.
- **A (empfohlen):** Du führst zuerst den Test aus: `"<python aus data\python.txt>" tests\live_dnd.py`. Er installiert das Paket nur in einen Temp-Ordner und öffnet ein Testfenster zum Ziehen. Wenn es klappt, schreibe "1 A klappt", dann trage ich es in `setup-windows.bat` ein (installiert es für alle).
- **B:** Ohne Drag and drop veröffentlichen (nur Strg+V, Paste, Add file). Dann baue ich nichts ein.
- **C:** Es soll immer mitinstalliert werden, ohne Test. Etwas riskanter: falls es bei dir nicht läuft, merkst du es erst im Fenster.

## 2. Der Knopf "Insert reference image" im Fenster
Er ist jetzt grau, weil die Slots ihn ersetzen. Ihn ganz zu entfernen betrifft Dateien einer anderen Lane (das Fenster-Layout).
- **A (empfohlen):** Lane L3 (Fenster-Politur) entfernt ihn mit ihrer nächsten Runde. Bis dahin bleibt er grau.
- **B:** Ich entferne ihn selbst, mit einer kleinen Änderung in zwei fremden Dateien. Gefahr: Konflikt beim Zusammenführen.

## 3. Freistellen: weißer oder grauer Hintergrund für das Referenzbild?
Wenn du ein Bild freistellst, ist der Hintergrund durchsichtig. Das Modell bekommt aber ein flaches Bild, also muss ich eine Farbe einsetzen. Du hattest vermutet, dass Weiß stört.
- **A:** Weiß (so ist es jetzt).
- **B (empfohlen zum Ausprobieren):** neutrales Grau. Ich baue es um, du vergleichst im Ergebnis.
- **C:** Ein Schalter im Slot, du wählst selbst.

## 4. Wo sollen die Slots erscheinen?
Jetzt: bei Edit, Fill Selection und Expand image, aber nur bei Modellen mit Slots (Qwen, Fibo, Flux 2, Flux 3). Bei Remove Selection, Upscale, Refine, MOSS, Krea gibt es keine.
- **A (jetzt so):** Edit, Fill und Expand.
- **B (empfohlen, wenn Expand mit Referenz bei dir nichts bringt):** nur Edit und Fill.
- **C:** nur Edit.

## 5. Beschreibung eines Referenzbilds (Knopf "Describe")
Qwen 3.5 9B schreibt zwei Sätze über das Bild. Jetzt landet der Text nur im Slot (beim Daraufzeigen) und unter den Slots. In deinen Text kommt er erst, wenn du auf "Descriptions to prompt" klickst.
- **A (empfohlen):** so lassen.
- **B:** Der Text wird sofort an deinen Prompt gehängt.
- **C:** Der Text wird jedes Mal automatisch geschrieben, wenn du ein Bild einfügst (kostet etwa 4 Sekunden GPU je Bild).

## 6. Bitte einmal ansehen, wenn du das Fenster startest (nur ein Eindruck genügt)
- Passen die drei Slots (je 108 Punkt breit) ins Fenster, auch bei 150 % Skalierung? Sonst mache ich sie schmaler.
- Sind die Knopf-Wörter klar: "Pen", "Cut out", "Describe", "Paste", "Add file", "Descriptions to prompt"? Sag mir andere Wörter, wenn dir etwas nicht gefällt.
- Der Hinweis unter den Slots ("Name them in your text: picture = <image1>, reference 1 = <image2>"): verständlich?

---
## Runde 2

## 7. Was macht „Multi Image Edit“ genau? (Aufgabe 1)
Ich habe den Modus mit der einfachsten Lösung gebaut, damit du ihn ausprobieren kannst. Ändern geht schnell.
- **Jetzt (A, empfohlen):** Es läuft der Edit-Workflow des Modells (Qwen, Fibo, Flux 2, Flux 3). Das ganze Bild wird bearbeitet, eine Auswahl wird ignoriert, es gibt keine Maske. Das Ergebnis kommt wie bei „Edit whole image“ als neue Ebene oben drauf.
- **B:** Mit Auswahl: Nur der ausgewählte Bereich wird bearbeitet (wie „Fill Selection“, aber mit den Referenzbildern).
- **C:** Ergebnis als neues Dokument statt als Ebene.

---
## Runde 3

## 8. Qwen mit 8 Referenzbildern: Grenze für 16 GB Grafikspeicher?
Der Qwen-Knoten kann bis zu 16 Bilder, ich habe wie gewünscht 8 Slots plus Hauptbild eingebaut. Jedes Referenzbild wird in seiner eigenen Größe (höchstens 1024 Punkt an der langen Seite) mitgegeben, mehr Bilder heißt mehr Speicher und längere Rechenzeit. Ich habe das NICHT gemessen und weiß nicht, ab wann deine Karte (16 GB) aussteigt.
- **A (empfohlen):** 8 Slots lassen, du probierst 2, 4 und 8 Bilder und sagst mir, wo es zu langsam wird oder abbricht. Die Obergrenze ist eine Zahl (`max_refs=8` in `models.py`).
- **B:** Gleich auf 4 setzen, bis du getestet hast.
- **C:** Die Bilder automatisch kleiner machen, je mehr es sind (z. B. 8 Bilder höchstens 512 Punkt). Das ändert aber, wie genau das Modell die Bilder sieht.

## 9. Flux 3 Boxen: Plan (noch nichts gebaut)
Du hast „Auswahl des Hauptbilds wird zur Box, je Slot ein Symbol ‚Auswahl als Ort verwenden‘ plus Beschreibung“ gewählt. Die Datei `docs/flux3-bbox-workflow-notes.md` ist in meinem Ordner nicht angekommen (mein Zweig `next` ist alt), ich habe sie nicht gelesen. Ich habe stattdessen in DEINEM ComfyUI nachgesehen, was installiert ist:
- `CreateBoundingBoxes` (Kernknoten): zeichnet Boxen auf einer Fläche. Es gibt einen optionalen Eingang `bboxes` (BOUNDING_BOX), also kann man Boxen auch per Workflow-Datei einspeisen, ohne zu zeichnen. Ausgabe `elements` (ARRAY).
- `Flux3LayoutPrompt` („FLUX 3 Image Layout Prompt“, Kernknoten): nimmt `prompt` (Text) und `element` (ARRAY) und gibt einen Text zurück; die Beschreibung sagt: hängt die Boxen als Layout-Tabelle an den Prompt. Das ist reine Textarbeit, kein Cloud-Aufruf. Ob Klein die Tabelle versteht, ist offen.
- `Flux3PromptBuilderKJ` (KJNodes): baut dieselbe Tabelle (JSON, Raster 0 bis 1000) und beschreibt ausdrücklich Referenzbilder: „A box drawn on a reference marks where an object is in it; … draw again [on the output] to place that object there.“ Mit `<id>` im Prompt bindet man Wörter an eine Box. Das ist genau das, was du vermutet hast, aber es steht in der Knotenbeschreibung, getestet ist es nicht.
Optionen für das Plugin:
- **A (empfohlen, erst testen):** Das Plugin baut die Tabelle selbst als Text und hängt sie an den Prompt (kein neuer Knoten nötig, falls Klein den Text versteht). Vorher muss ich das genaue Tabellenformat kennen: ich lasse in ComfyUI einmal `Flux3LayoutPrompt` oder `Flux3PromptBuilderKJ` mit einer Box laufen und lese den ausgegebenen Text. Das braucht einen kurzen Lauf, ohne Bildmodell (nur Text), also praktisch keine GPU.
- **B:** Das Plugin speist die Box in `CreateBoundingBoxes` + `Flux3LayoutPrompt` im Workflow ein (zwei neue Knoten im Flux-3-Workflow, Box als Zahlen aus der PhotoCraft-Auswahl).
- **C:** Weiter von Hand testen und nichts im Plugin bauen.
Noch zu testen (ein Bildlauf, braucht deine Erlaubnis für die GPU): Versteht lokales Flux 3 Klein die Tabelle und hält es die Box ein? Und platziert es ein Referenzbild dort? Sag mir, ob ich die beiden kurzen Textläufe (ohne GPU-Bild) jetzt machen darf.
Ergänzend: PhotoCraft liefert die Auswahl als Rechteck-Maske; daraus lässt sich die Box (0 bis 1000) einfach ausrechnen. Eine unregelmäßige Auswahl würde auf ihr Umschlagrechteck reduziert.
