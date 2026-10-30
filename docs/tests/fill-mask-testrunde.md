# Fill-Masken-Testrunde (30.10.)

Warum: Bei Fill mit Qwen und Fibo schneidet der schmale weiche Rand von heute den Rand der Füllung und ihren Schatten ab (28.10.). Mit Dichte 5 % (heutiger Startwert) ist dagegen fast der ganze neu gemalte Ausschnitt sichtbar, und seine gerade Kante kann sich zeigen. Der Versuch vom 28.10. (Maske läuft bis zum Rand des Ausschnitts aus) wurde zurückgenommen, weil die Füllung an einer Bildkante weich wurde. Vor einem neuen Anlauf deshalb ein großer Test (deine Entscheidungen vom 30.10.: zwei Stufen, alle vier Varianten, Bilder aus `A:\testpics3\resized_1280px`; die Runde danach auf ein Viertel gekürzt).

Qwen und Fibo sehen die Maske beim Generieren nicht. Darum gibt es je Fall **eine** Generierung, und alle vier Masken werden auf dasselbe Ergebnis gelegt:

| Variante | Was sie macht |
|---|---|
| heute: schmaler Rand | Auswahl voll deckend, weicher Rand außen, so breit wie Edge feather |
| heute: Dichte 5 % | dieselbe Maske mit 5 % Dichte: der ganze Ausschnitt ist zu 95 % oder mehr sichtbar |
| bis zum Ausschnittrand | Auswahl und Edge feather voll deckend, dann weich bis 0 an den Seiten des Ausschnitts (der Versuch vom 28.10.) |
| breiter Rand außen (3×) | wie heute, dreimal so breit |

Der Code der Varianten steht in `pccomfy/fillmask.py`. Das Plugin selbst ist unverändert, bis du den Sieger wählst.

## Stufe 1: ohne GPU (erledigt 30.10.)

`tests/test_fill_mask_variants.py` (läuft mit allen Tests): jede Variante an 8 Positionen (Mitte, jede Bildkante berührt, zwei Ecken, 3 px neben der Kante), als Rechteck und als harter Lasso, mit Edge feather 4 / 10 / 20 % und Context 0.2 / 0.4 / 0.8, also 144 Fälle je Variante. Die Regeln:

1. Die Auswahl ist voll deckend, auch dort, wo sie die Bildkante berührt.
2. Zur Bildkante hin läuft keine Maske aus (verglichen mit derselben Maske, bei der das Bild weitergeht).
3. An den Seiten des Ausschnitts im Bild: „bis zum Ausschnittrand“ ist 0. Schmal und breit lassen höchstens eine Spur übrig. Dichte 5 % zeigt überall mindestens 95 %.
4. „Schmal“ ist genau die Maske, die das Plugin heute baut. Ecken laufen so weit aus wie Kanten.

**Ergebnis:** Alle vier Varianten halten alle Regeln ein. **Keine läuft an einer Bildkante aus.** Ein absichtlich eingebauter Fehler dieser Art wird erkannt. Der Fehler vom 28.10. lag also nicht in der Form der Maske. Was damals weich aussah, soll Stufe 2 zeigen (Häkchen „Füllung am Bildrand weich“). Nebenbefund: An den Seiten des Ausschnitts lässt „schmal“ höchstens 5 von 255 Stufen übrig, „breit“ höchstens 12 (etwa 5 %).

## Stufe 2: echte Läufe (wartet auf dich)

**Bilder** (aus `A:\testpics3\resized_1280px`): Zimmer mit Klavierrahmen (`IMG_20240522_194039_1`), Waldschlucht (`IMG_20240921_102651`), Wand mit Ukulelen (`IMG_20241001_155006`), Weg im Freien (`IMG_20241123_142913`).

**Positionen:** Mitte (je Bild eine freie Stelle), linke Kante, obere Kante, Ecke oben links, Ecke unten rechts. Die Auswahl ist 26 % der Bildbreite × 32 % der Bildhöhe groß und berührt bei den Kanten- und Eckpositionen die Bildkante. Rechteck und harter Lasso (ohne Glättung: Eine geglättete Auswahl lässt das Plugin ohnehin, wie sie ist) wechseln sich je Bild und Position ab, sodass jedes Bild und jede Position beide Formen bekommt. Fibo und Qwen bekommen im selben Fall dieselbe Auswahl. Übersicht aller Auswahlen mit den Objekten: `data/fill-mask-test/vorschau-auswahlen.png`.

**Objekte** (Dinge, die Schatten werfen):

| Bild | Mitte | links | oben | oben links | unten rechts |
|---|---|---|---|---|---|
| Zimmer | a wooden stool standing on the floor | a tall potted plant | a framed picture hanging on the wall | a round wall clock | a cardboard box on the floor |
| Waldschlucht | a large mossy boulder | a fallen tree trunk | a small wooden hut | a wooden signpost | a hiking backpack on the ground |
| Ukulelen | a framed landscape painting on the wall | a tall floor lamp | a round wall clock | a wall shelf with books | a potted plant on the floor |
| Weg | a park bench beside the path | a red mailbox on a post | a hot air balloon | a red kite in the sky | a dog sitting on the grass |

**Umfang** (auf ein Viertel gekürzt, Wunsch des Users 30.10.): 4 Bilder × 5 Positionen × Fibo und Qwen = **40 Läufe**, 1 Seed, Context 0.4, je Modell mit den Fill-Startwerten (Edge feather Fibo 10 %, Qwen 4 %; Fibo mit Seam-Korrektur). Geschätzt etwa 12 bis 15 Minuten, die GPU ist in der Zeit belegt.

### Starten

ComfyUI muss laufen, mit den Fibo- und Qwen-Dateien. Im Plugin-Ordner in die Adresszeile des Explorers `powershell` tippen, Enter, dann:

```
.venv\Scripts\python.exe tests\live_fill_mask.py run --images "A:\testpics3\resized_1280px"
```

Am Ende steht „DONE … cases, 40 to rate“.

### Bewerten (blind)

```
.venv\Scripts\python.exe tests\live_fill_mask.py rate
```

Es sind alle 40 Fälle: jedes Bild, jede Position und jedes Modell einmal. Je Fall siehst du die vier Varianten nebeneinander, in zufälliger Reihenfolge und ohne Namen, als Ausschnitt um die Auswahl herum (die Seiten des neu gemalten Bereichs sind mit drin).

- **1 / 2 / 3 / 4** = bestes Bild, **← / →** blättern, **O** zeigt die Auswahl als orange Linie, **V** zeigt das ganze Bild.
- Unter jedem Bild ankreuzen, was nicht stimmt: Schatten/Rand der Füllung abgeschnitten, gerade Kante des Ausschnitts sichtbar, Farb-/Helligkeitsfleck um die Auswahl, Füllung am Bildrand weich. Eine Notiz, wenn nötig.
- Alles wird sofort gespeichert. Du kannst schließen und später weitermachen (es startet beim ersten unbewerteten Fall).

### Auswerten

```
.venv\Scripts\python.exe tests\live_fill_mask.py summary
```

Das schreibt `ergebnis.md` in den Ordner der Runde (`data\fill-mask-test\<Zeit>\`). Darin stehen die Messung über alle 40 Fälle (Sprung an den Seiten des Ausschnitts, Anteil der Änderungen außerhalb der Auswahl, der sichtbar bleibt), die Blindbewertung je Modell und Variante und das beste Bild je Position. Danach einfach „Fertig“ sagen; ich lese den Ordner selbst und lege dir die Optionen für den Einbau vor.
