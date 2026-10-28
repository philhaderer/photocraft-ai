# Testrunde E2: Context und Edge feather, Rechteck und runde Auswahl

Stand 2026-10-28. Ziel: feste Startwerte für Context und Edge feather je Modell und Funktion, und eine Antwort auf die Frage, ob runde und eckige Auswahlen verschiedene Einstellungen (oder Tooltips, oder eigene Modi) brauchen. Du machst die Läufe, ich trage die Werte danach in `pccomfy/models.py` ein (mit Tests).

## Vorbereitung (einmal)

- Ein Testbild mit klaren Flächen und einer Kante, an der man Übergänge gut sieht (Himmel, Wand, Boden). Immer dasselbe Bild.
- Unter dem Negative prompt: **Seed fest** (eine Zahl eintragen statt -1), **Variants 1**. Dann unterscheidet sich ein Lauf vom nächsten nur durch den Wert, den wir prüfen.
- Pro Zeile: Werte einstellen, kurz **Show feather** ansehen, dann Generate. Mit Undo (im Plugin) zurück zum Ausgangsbild vor dem nächsten Lauf.
- **Zwei Auswahlen** je Modell, immer an derselben Stelle und etwa gleich groß:
  - **R** = Rechteck (Rectangular Marquee)
  - **E** = Ellipse oder Lasso (geglättet). Hinweis: Eine geglättete Auswahl gilt beim Plugin schon als weich, Edge feather wirkt dann kaum. Genau das wollen wir im Bild sehen.

## Heutige Startwerte

| Modell | Funktion | Context | Edge feather |
|---|---|---|---|
| Qwen 2.1 | Fill | 0.4 | 4 % |
| Qwen 2.1 | Remove | 0.4 | 10 % |
| Fibo | Fill | 0.2 | 10 % |
| Fibo | Remove | 0.4 | 10 % |
| Flux 2 / Flux 3 | Remove | 0.4 | 10 % |

Deine Referenz vom 28.10.: Fibo, Rechteck, soft, **6,5 %** ist gut.

## Runde 1: Qwen Fill (Prompt z. B. „a red flower“)

| # | Auswahl | Context | Feather | Urteil (gut / geht / schlecht) | Notiz |
|---|---|---|---|---|---|
| 1 | R | 0.4 | 4 % | | |
| 2 | R | 0.6 | 4 % | | |
| 3 | R | 0.8 | 4 % | | |
| 4 | R | bester aus 1–3 | 6.5 % | | |
| 5 | E | bester aus 1–3 | 4 % | | |

Worauf achten: passt das Objekt in Größe und Licht? Sieht man die Kante des Ausschnitts (gerade Linie im Bild)? Ist der Rand des Objekts zu hart oder verwaschen?

## Runde 2: Fibo Fill (gleicher Prompt)

| # | Auswahl | Context | Feather | Urteil | Notiz |
|---|---|---|---|---|---|
| 6 | R | 0.2 | 10 % | | |
| 7 | R | 0.2 | 6.5 % | | |
| 8 | R | 0.4 | 6.5 % | | |
| 9 | E | bester aus 6–8 | (wirkt kaum) | | |

## Runde 3: Remove (kurz, ein Objekt entfernen)

| # | Modell | Auswahl | Context | Feather | Urteil | Notiz |
|---|---|---|---|---|---|---|
| 10 | Qwen | R | 0.4 | 10 % | | |
| 11 | Qwen | R | 0.6 | 10 % | | |
| 12 | Fibo | R | 0.4 | 10 % | | |
| 13 | Fibo | E | 0.4 | (wirkt kaum) | | |

Flux 2 / Flux 3 Remove lasse ich weg (laut Tooltip „works only sometimes“); sag, wenn du sie dabeihaben willst.

## Danach (Fragen an dich)

1. Welche Werte werden die neuen Startwerte? (Ich schlage sie aus deinen Urteilen vor, du bestätigst.)
2. Runde Auswahl: genügt ein Tooltip („Rechteck: das Plugin macht den weichen Rand; runde Auswahl / Lasso: schon weich, Edge feather wirkt kaum“), oder soll es eigene Startwerte bzw. einen eigenen Modus geben?

## Ergebnis (User, 28.10.)

- **Qwen Fill:** Rechteck: Standardwerte am besten (Context 0.4, 4 %). Runde Auswahl: kein klarer Gewinner, Standardwerte bleiben.
- **Fibo Fill:** Rechteck und rund: kein klarer Gewinner, aber Context 0.4 besser als 0.2. **Neuer Startwert Context 0.4.**
- **Remove:** Qwen und Fibo bleiben bei 0.4 / 10 %.
- Fibo ist insgesamt besser: im Easy Mode bei Fill und Remove zuerst. Kein eigener Modus für Rechteck und Lasso.
- Befunde: die Maske einer Rechteck-Auswahl hatte harte Ecken (behoben: Abstand statt Unschärfe); Qwen Fill macht Objekte kleiner als Fibo Fill (offen).
- Remove wiederholte sich bis zu 3-mal von selbst; jetzt ein Lauf, Tipp/Tooltip bei Fibo schlägt einen zweiten Versuch von Hand vor.
