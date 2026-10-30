# Flux 3 Klein: Objekte per Box ersetzen (Notizen aus dem Workflow des Nutzers)

Quelle: ComfyUI-Bibliothek des Nutzers, `image_flux3_klein_distilled_image_edit_bbox test.json` (vom Nutzer getestet: "funktioniert").
Stand 2026-10-26. Das ist eine Beschreibung, noch nichts davon ist im Plugin gebaut.

## Aufbau des Workflows (lokales Flux 3 Klein, nicht der Cloud-Knoten)
- Modell: `flux3-image-klein-int8-convrot.safetensors`, Textencoder `qwen3vl_4b_int8_convrot.safetensors` (CLIPLoader, Typ `flux3`), VAE `flux2-vae.safetensors`. KSampler: 16 Steps, cfg 1, euler/simple.
- Bilder: LoadImage 11 (das Hauptbild) und LoadImage 54 (Referenz) gehen in `ReferenceMultiLatent` als `images.image0` und `images.image1` (Auflösung "resize", 1 Megapixel).
- Boxen: `CreateBoundingBoxes` (ComfyUI-Kernknoten, Größe 1600 x 1200, Hintergrund = Hauptbild). Seine Ausgabe `elements` (Array) geht in `Flux3LayoutPrompt` (Kernknoten, Eingabe `element` + `prompt`). Die gespeicherte Datei hat `editor_state: []`: die Boxen werden in der ComfyUI-Oberfläche gezeichnet und stehen nicht in der Datei.
- Der Text, den der Nutzer eingetragen hat (Eingabe `prompt` von `Flux3LayoutPrompt`):
  `In <ref_image_0>, replace the tent <obj_1> with <ref_image_1> a little dog with a red ball in his mouth`
- Danach ein Schalter (`ComfySwitchNode`, Standard "false"): entweder geht der Layout-Prompt direkt an `CLIPTextEncode` (on_true), oder zuerst durch den Prompt-Upsampler (`TextGenerate` mit `qwen3.5_9b_flux3_prompt_upsampler_w4a8`, Systemprompt `Text (System prompt)`; er sieht nur das Hauptbild, weil `BatchImagesNode` nur image0 enthält). Ob der Nutzer mit oder ohne Upsampler getestet hat, ist aus der Datei nicht ersichtlich.

## Was daraus folgt
- Die Bild-Tags für Flux 3 Klein sind **`<ref_image_0>` (Hauptbild), `<ref_image_1>` (erste Referenz) ...**, also zählen sie ab 0. Das passt zu `Model.tag_style` für Flux 3 (`<ref_image_{i}>`); damit ist die Annahme aus `docs/entscheidungen-L2.md` jetzt durch den Workflow des Nutzers belegt.
- Eine Box wird im Prompt als **`<obj_N>`** angesprochen (N zählt ab 1 in der Reihenfolge der Boxen). Jede Box hat eine Beschreibung ("desc"); es gibt auch Text-Boxen mit genauem Text (Typ "text").
- Box-Format im Array `elements`: `bbox = [ymin, xmin, ymax, xmax]` auf einer Skala 0 bis 1000, Felder `type` ("obj" oder "text"), `desc`, optional `text`. Farbpaletten ignoriert Flux 3 (Farben in die Beschreibung).
- Es ist nicht geklärt, ob man die Boxen von außen (das Plugin per API) in `CreateBoundingBoxes` geben kann: der Knoten hat eine Eingabe `bboxes` (JSON, Boxen oder Elements), aber auch einen Editor-Zustand. Das muss mit einem echten Lauf geprüft werden. Alternative: das Plugin baut die Layout-Tabelle selbst und lässt `CreateBoundingBoxes` weg.
- Idee für PhotoCraft (Entscheidung steht aus): die PhotoCraft-Auswahl ist die Box. Jeder Slot bekommt einen Marker-Knopf "Auswahl als Platz für dieses Bild", dazu eine Beschreibung. Aus Slot und Box baut das Plugin den Satz im obigen Muster.

## Ergebnis des Textlaufs (30.10., ComfyUI 0.42.0, ohne Sampling, ohne GPU)

Graph: `CreateBoundingBoxes` (1600 x 1200) -> `Flux3LayoutPrompt` -> `PreviewAny`, per `/prompt` geschickt. Skript im Scratchpad der Sitzung, nicht im Repo.
- **Die API nimmt die Boxen von außen an.** Eingabe `bboxes` von `CreateBoundingBoxes` als JSON-String. Zwei Formen laufen:
  - Pixel-Form: `[{"x":100,"y":300,"width":400,"height":500,"metadata":{"type":"obj","desc":"a green tent","text":"","palette":[]}}]` (Pixel auf der Fläche width x height). Das passt zur PhotoCraft-Auswahl.
  - Elements-Form: `[{"type":"obj","bbox":[ymin,xmin,ymax,xmax],"desc":"a tent"}]` (Skala 0 bis 1000); `"type":"text"` mit `"text":"HELLO"` wird zu `desc: sign "HELLO"`.
- **Stolperstein:** `editor_state` ist Pflicht, und eine leere Liste `[]` lehnt die API als „Bad linked input“ ab. Es geht mit `{"__value__": []}`.
- **Ausgabe von `Flux3LayoutPrompt`:** der Prompt, ein Leerzeichen, dann die Tabelle als JSON-Text, z. B. `... in his mouth [{"id": "obj_1", "bbox": [250, 62, 667, 312], "desc": "a green tent"}]`. `bbox` ist `[ymin, xmin, ymax, xmax]` auf 0 bis 1000, aus der Pixel-Box umgerechnet (300/1200, 100/1600 ...). Ohne `metadata.desc` bleibt `desc` leer.
- **Folge:** Das Plugin kann die Boxen aus der PhotoCraft-Auswahl in Pixeln an `CreateBoundingBoxes` übergeben (Option 1), oder die Tabelle selbst als Text anhängen und beide Knoten weglassen (Option 2: gleiches Ergebnis, ein Knoten weniger, aber das Format hängt dann am Plugin, nicht an ComfyUI).
- **Nicht geprüft:** ob Flux 3 mit solchen Boxen ein gutes Bild macht (kein Sampling gelaufen), und ob der Prompt-Upsampler die Tabelle erhält.

## Echter Lauf (30.10., Flux 3 Klein, Seed 7, 15 Steps; Bilder in `data/flux3-bbox-test/`, nicht im Repo)

Aufbau wie im Plugin: Graph aus `flux3-klein-edit.json` mit `workflows.add_layout`, Referenz in Slot 1, Prompt nur „clock“ (+ „Place the result in <obj_1>.“). Vier realistische Szenen (Flux 3 Text to image: Wohnzimmer, Küche, Büro, Altstadtgasse), zwei Uhren als Referenz; Vergleich ohne Box (Kontrolle).
- **Die Box funktioniert:** In allen 4 Szenen sitzt die Uhr in der Box (Wohnzimmer über dem Sideboard, Küche an der Wand neben den Regalen, Büro oben an der Wand, Gasse an der Fassade). Ohne Box setzt Flux 3 die Uhr irgendwohin: auf das Sideboard, groß vor den Herd, auf den Laptop-Bildschirm; in der Gasse gar nicht sichtbar.
- **Test mit der Schlichtbild-Szene (Haus, Fuchs):** eigener `<obj_1>` im Prompt und der angehängte Satz geben beide den Fuchs in die Box.
- **Nachteil: das ganze Bild ändert sich ein wenig.** Mittlere Abweichung außerhalb der Box (0 bis 255): 4,5 bis 14,6 mit Box, 6 bis 13 ohne (Kontrolle). Sichtbar: Möbel, Teppich, Fenster leicht anders; in der Schlichtszene wanderte das Haus. Das ist Flux 3 selbst, nicht die Box.
- **Abhilfe getestet (nur am Bild, nicht im Plugin):** das Ergebnis nur innerhalb der Box (Rechteck, weicher Rand ca. 12 px) über das Original legen; der Rest bleibt bildgleich, die Uhr sieht gleich aus.

## Großer Testlauf (30.10.): Referenzen aus dem Netz, Maskenvarianten, mehrere Boxen

Bilder in `data/flux3-bbox-test/` (nicht im Repo): `web-refs/` (Wikimedia Commons, nur CC0/Public domain, `SOURCES.md` nennt Datei und Seite), `inputs/` (mit Flux 3 erzeugte realistische Szenen und moderne Referenzen), `big/`, `multi/` und die Blätter `big_sheet1.png`, `big_sheet2.png`, `margin_sheet.png`, `multi_sheet.png`, `multi_sheet2.png`.

**10 Fälle** (Stuhl, Sessel s/w, Hocker, Frau, Mann, altes Paar, Tasse, Vase, Uhr, historische Karte als Person; Szenen: Esszimmer, Park, Café, Tisch), Prompt nur das Wort + „Place the result in <obj_1>.“, Seed 7:
- **Platzierung:** in allen 10 Fällen sitzt das Objekt in der Box (Position stimmt).
- **Größe:** die Box ist nur ein Anhalt. Flux 3 zeichnet Möbel und Personen oft größer als die Box (Stuhl: ca. 1,5-fache Höhe). Historische Referenzen (s/w, Karte) kommen mit ihrem Stil (grau, Kartenrand) ins Bild, auch als Person.
- **Rest des Bildes:** mittlere Abweichung außerhalb der Box 5 bis 13 (0 bis 255), bei Personen am höchsten (12 bis 13).
- **Nur-in-der-Box einfügen:** mit dem genauen Box-Rechteck wird ein größeres Objekt angeschnitten (Stuhllehne, Karte); mit einem Ellipsen-„Lasso“ noch mehr (Ecken fehlen). Mit 40 % Rand um die Box bleiben fast alle Objekte ganz (nur die Stuhllehne bleibt leicht angeschnitten). Daraus: die Maske braucht Rand (Vorschlag 50 %), oder der Nutzer zieht die Box großzügig.

**Mehrere Boxen (drei Referenzen auf einmal):** `CreateBoundingBoxes` nimmt eine Liste, `Flux3LayoutPrompt` nummeriert in Eingabereihenfolge (`obj_1`, `obj_2`, `obj_3`; ohne Umsortieren geprüft). Prompt: „Place <ref_image_1> in <obj_1>. Place <ref_image_2> in <obj_2>. Place <ref_image_3> in <obj_3>.“
- Reihenfolge links, rechts, Mitte: alle drei Referenzen am richtigen Ort.
- Vertauschte Boxen, ohne Beschreibung der Boxen: nur Referenz 1 stimmt, 2 und 3 sind in 3 von 3 Seeds vertauscht (Seeds 7, 8, 9).
- **Vertauschte Boxen mit `desc` je Box** („a wooden chair“, „a red plastic stool“, „a green porcelain vase“): alle drei stimmen, 3 von 3 Seeds. `desc` aus der Beschreibung des Slots (Describe-Knopf) oder einem Text des Nutzers ist also nötig.
- Eine Referenz im Slot, die der Prompt nicht nennt, taucht trotzdem im Bild auf (Vase mit Stuhl vermischt): nur die benutzten Slots mitschicken.
- Offen für den Bau: PhotoCraft kennt nur eine Auswahl; mehrere Rechtecke darin haben keine Reihenfolge. Vorschlag: Knopf je Slot „Auswahl als Box für dieses Bild“, der das Rechteck der aktuellen Auswahl für den Slot merkt (Box k gehört zu Referenz k).
