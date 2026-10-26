# Der gesendete Prompt bei „Multi Image Edit“

Diese Datei wird von `python tests/test_prompt_aufbau.py --write` erzeugt: Die Beispiele sind die echte Ausgabe der echten Funktionen (Slots, Fenster, Bridge, Workflow), kein von Hand geschriebener Text.

## Aufbau

1. Das Bild im PhotoCraft-Dokument ist immer „Bild 1“. Die Referenzbilder sind Bild 2, 3 … (Reihenfolge der Slots).
2. Du tippst deinen Text und nennst die Bilder mit ihren Namen (unter den Slots steht, wie sie heißen).
3. Hat ein Referenzbild eine Beschreibung, wird sie automatisch ans Ende deines Textes gehängt, eine Zeile pro Bild: `<Name>: <Beschreibung>`.
4. Der Workflow setzt den Namen des Hauptbildes vorn davor, wenn das Modell einen braucht (`pc_image_tag`).
5. Das Textfeld im Fenster bleibt unverändert; das Anhängen passiert erst beim Senden.

Beispiel in allen vier Fällen: zwei Referenzbilder (Hund, Mütze), beide beschrieben.

## Qwen 2.1 Edit

Namen: Bild = `<image1>`, Referenzen = `<image2>`, `<image3>`

Dein Text:

```
Put the hat from <image3> on the dog from <image2>.
```

Gesendet an den Text-Encoder:

```
<image1> Put the hat from <image3> on the dog from <image2>.
<image2>: A brown dog with a red collar, sitting on grass.
<image3>: A blue knitted hat with a white pompom.
```

## Fibo 2.0 Edit

Namen: Bild = `<image_1>`, Referenzen = `<image_2>`, `<image_3>`

Dein Text:

```
Put the hat from <image_3> on the dog from <image_2>.
```

Gesendet an den Text-Encoder:

```
Put the hat from <image_3> on the dog from <image_2>.
<image_2>: A brown dog with a red collar, sitting on grass.
<image_3>: A blue knitted hat with a white pompom.
```

## Flux 2 Klein Edit

Namen: Bild = `image 1`, Referenzen = `image 2`, `image 3`

Dein Text:

```
Put the hat from image 3 on the dog from image 2.
```

Gesendet an den Text-Encoder:

```
Put the hat from image 3 on the dog from image 2.
image 2: A brown dog with a red collar, sitting on grass.
image 3: A blue knitted hat with a white pompom.
```

## Flux 3 Klein Edit

Namen: Bild = `<ref_image_0>`, Referenzen = `<ref_image_1>`, `<ref_image_2>`

Dein Text:

```
Put the hat from <ref_image_2> on the dog from <ref_image_1>.
```

Gesendet an den Text-Encoder:

```
Put the hat from <ref_image_2> on the dog from <ref_image_1>.
<ref_image_1>: A brown dog with a red collar, sitting on grass.
<ref_image_2>: A blue knitted hat with a white pompom.
```

## Sieht man den gesendeten Prompt im Betrieb?

`data/exchange/runs.jsonl` hat pro Lauf eine Zeile mit dem Prompt (Feld `prompt`). Das ist dein Text plus die angehängten Beschreibungen, aber ohne den Bildnamen, den der Workflow davorsetzt, und bei langen Texten nach 600 Zeichen abgeschnitten. Der Text, der wirklich beim Encoder ankommt, steht in `data/exchange/last-graph.json` (nur der letzte Lauf). Für den Alltag reicht `runs.jsonl`; für die Frage „was genau sah das Modell?“ nimm `last-graph.json`.
