# Prompting für „Multi Image Edit“

Stand 2026-10-26. Der Text trennt strikt: **A** belegt (mit Quelle), **B** von dir von Hand getestet, **C** Vermutung. Das Plugin verfeinert den Prompt nicht automatisch; es hängt nur die Beschreibungen an (siehe `docs/prompt-aufbau.md`).

## Wie das Plugin die Bilder nummeriert
Das Bild im PhotoCraft-Dokument ist Bild 1, Slot 1 ist Bild 2, Slot 2 Bild 3 usw. Die Schreibweise je Modell: Qwen `<image2>`, Fibo `<image_2>`, Flux 2 `image 2`, Flux 3 `<ref_image_1>` (Flux 3 zählt ab 0: `<ref_image_0>` ist das Hauptbild). Beim Modellwechsel schreibt das Fenster die Namen im Prompt automatisch um.

## A. Belegt (Hersteller und Doku)
- **FLUX.2 (BFL-Doku):** 1 bis 10 Referenzbilder. „The first entry is ‚image 1‘.“ Mehrere Bilder spricht man über die Position an („image 1“, „image 2“). Gebt jedem Bild eine klare Rolle im Prompt (Beispiel der Doku: Bild 1 ist das Motiv, Bild 2 der Stil). Bei Seitenverhältnis „auto“ folgt das Ergebnis dem ersten Bild; das Bild mit dem gewünschten Seitenverhältnis kommt zuerst. Quelle: https://docs.bfl.ai/guides/prompting_editing_overview
- **FLUX.2 klein (fal.ai-Leitfaden, Drittanbieter):** Bilder über ihre Reihenfolge ansprechen; Beispiel: „The subject from the first image wearing the jacket from the second image, photographed in the environment from the third image.“ Eine Höchstzahl nennt der Leitfaden nicht. Quelle: https://fal.ai/learn/devs/flux-2-klein-prompt-guide
- **ComfyUI-Knoten „FLUX 3 Image“ (Cloud-Knoten):** bis zu 10 Referenzbilder; im Prompt „image 1, image 2, and so on“. Quelle: https://docs.comfy.org/built-in-nodes/Flux3ImageNode.md
- **Qwen Image 2.1 (ComfyUI-Knoten `TextEncodeQwenImage21`, per Abfrage deines ComfyUI):** bis zu 16 Bild-Eingänge; mit `resolution` 0 behält jedes Referenzbild seine Größe (Vielfache von 32). Das Tag-Muster `<imageN>` steht nicht in dieser Abfrage.
- **Knotenbeschreibung in deinem ComfyUI (`Flux3PromptBuilderKJ`, KJNodes):** Boxen werden als JSON-Tabelle (Raster 0 bis 1000) an den Prompt gehängt, mit `<id>` im Prompt bindet man Wörter an eine Box; bei Referenzbildern „a box drawn on a reference marks where an object is in it; … draw again [on the output] to place that object there“. Das ist die Beschreibung des Knotens, kein Test mit Flux 3 Klein.
- **Flux 3 Layout-Prompt (ComfyUI-Doku):** Layout-Tabelle über Boxen (`<obj_N>`), gehört zum Cloud-Knoten. Referenzbilder werden dort nicht per Box platziert (nicht beschrieben). Siehe `docs/flux3-bbox-workflow-notes.md` (Haupt-Chat).

## B. Handtests (von dir)
- „the woman in `<image2>` is sitting on a beach“ auf einer **leeren weißen Fläche** als Hauptbild funktioniert.
- Freistellen (Cut out) und Drag and Drop funktionieren.
- Weiter ist noch nichts von Hand bestätigt. Trag neue Ergebnisse hier ein (Modell, Prompt, Ergebnis).

## C. Offene Vermutungen (nicht belegt)
- Das Tag-Muster `<ref_image_{i}>` für das **lokale** Flux 3 Klein ist eine eigene Annahme. Belegt ist nur „image 1, image 2“ für den Cloud-Knoten. Wenn Flux 3 die Bilder nicht erkennt, zuerst `image 2` statt `<ref_image_1>` probieren.
- Ob Fibos `<image_N>` und Qwens `<imageN>` die besten Schreibweisen sind, ist aus den Beispielen der Hersteller übernommen, nicht verglichen.
- Eine kurze Rolle je Bild („the dog in image 2“, „the hat from image 3“) hilft vermutlich; für Klein-Modelle ist das aus dem BFL-Rat (A) abgeleitet, nicht getestet.
- Beschreibungen am Prompt-Ende (so hängt das Plugin sie an) können helfen oder verwirren; unbekannt.
- Platzieren von Referenzbildern per Box (Flux 3) ist nicht belegt und müsste getestet werden.
- Mit vielen Referenzbildern (Qwen bis 8) sind Qualität, Zeit und Speicher auf 16 GB unbekannt.

## Wie du hier weiterkommst
Teste von Hand in ComfyUI, trag das Ergebnis unter B ein, dann ziehe ich Tag-Schreibweisen oder die Reihenfolge im Plugin nach. Keine Prompt-Automatik, bis du es willst.
