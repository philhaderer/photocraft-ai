# Fibo Expand: A/B-Test des Wortlauts (28.10.)

Anlass: Fibo ließ bei Expand den neuen Rand oft weiß (Bug „Expand füllt nicht auf Transparenz“, PLAN E3). Ursache war nicht die Transparenz: Das Plugin schickt jedem Modell den Rand weiß, egal ob er im Dokument transparent oder weiß ist (kopflos und im PhotoCraft des Users geprüft). Fibo selbst malte ihn nicht aus.

Aufbau: Fibo 2 Edit Turbo, 4 Schritte, direkt in ComfyUI (ohne PhotoCraft). Gemessen: Anteil des Randes, der weiß bleibt (Pixel ≥ 240), und die mittlere Änderung des bestehenden Bildes. „Gefüllt“ = weniger als 5 % Weiß übrig. Skripte und Bilder lagen im Scratchpad der Sitzung.

## Runde 1: zwei Bilder, an denen Fibo gescheitert war (Rand links), 6 Wortlaute × 3 Seeds

| Wortlaut | gefüllt | Weiß übrig |
|---|---|---|
| W2 „Replace the white area on the left with a seamless continuation of the scene. Keep the existing picture unchanged.“ | 6/6 | 0,6 % |
| W4 „Remove the white area on the left: fill it with the continuation of the scene.“ | 4/6 | 3 % |
| W3 langer „Outpaint …“-Satz | 1/6 | 58 % |
| W0 bisher: „Replace white (The white margin … leave no white. Keep the existing picture unchanged.)“ | 1/6 | 70 % |
| W5 „Complete the image …“ | 0/6 | 95 % |
| W1 nur „Replace white“ | 0/6 | 100 % (und das Bild ändert sich stark) |

## Runde 2: andere Seiten, W0 gegen W2, 2 Bilder × 2 Seeds

| Rand | W0 gefüllt | W2 gefüllt |
|---|---|---|
| rechts | 2/4 | 4/4 |
| oben | 2/4 | 4/4 |
| unten | 2/4 | 4/4 |
| links + unten | 2/4 | 4/4 |
| oben + rechts | 2/4 | 4/4 |
| rechts, W2 mit Beschreibung | – | 4/4 |

Das bestehende Bild ändert sich mit W2 nicht mehr als mit W0.

Auffällig beim Ansehen: einmal (Rüstungssaal, oben + rechts) ist die Füllung dunkel statt Raum; mit eingetippter Beschreibung („a hiker in a sunny forest“) malte Fibo den Wanderer ein zweites Mal in den Rand. Eine Beschreibung der Person bei Expand führt also zu Doppelungen.

**Gebaut** (`feat/fibo-expand-wording`): Fibo bekommt `FIBO_OUTPAINT_PROMPT` (W2, Seiten eingesetzt, eingetippter Text im Satz). Qwen und Flux behalten W0 (Qwen Expand ist „perfekt“). Live-Test durch den User offen.
