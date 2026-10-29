# Flux 3 Expand: alt gegen Outpaint-LoRA (29.10.)

**Anlass:** Der User meldete, dass Flux 3 Expand das Bild nur vergrößert, statt den neuen Rand zu füllen. Laut der Anleitung von Pixaromas Workflow „14. Flux 3 Klein - Outpaint“ hat der Autor der Outpaint-LoRA (ausboss) gemessen, dass Flux 3 ohne die LoRA das Bild in 36 von 40 Läufen verschiebt oder hineinzoomt.

**Varianten**

| | alt | neu |
|---|---|---|
| Workflow | `flux3-klein-edit.json` | `flux3-klein-outpaint.json` (Outpaint-LoRA 1,5, 16 Schritte) |
| Rand | weiß | grau #808080 (Trainingsfarbe der LoRA) |
| Prompt | Beschreibung + „replace white“ + Hinweis | Satz der LoRA + „Scene:“ + Beschreibung |
| Base res. / Context | 1536 / 0,4 | 1024 (ca. 1 MP) / 1,0 |

**Aufbau:** Die 8 Bilder des Users aus der Seam-Runde (aus deren Ergebnis ausgeschnitten, abseits der alten Naht), je Rand rechts 35 % und links + unten 25 %, Seeds 11 und 22, Beschreibung der Umgebung aus der Seam-Runde als Text; 64 Läufe. Nachgebaut wie die Bridge (ohne PhotoCraft, Ebenenmaske „none“). Skript im Scratchpad der Sitzung, Bilder in `data/flux3-expand-test/20261029-184022/` (`vergleich_1.jpg` … `vergleich_8.jpg`, `ergebnis.json`).

**Messung**

- Verschiebung (mittlere Abweichung des Originalteils, Werte über 15 = verschoben oder gezoomt): **alt 10 von 32, neu 0 von 32** (Median alt 7,6, neu 5,8). Die alten Ausreißer liegen fast alle beim Rand links + unten.
- Rand nicht gefüllt: alt 1, neu 2 Läufe über 5 % „flache“ Fläche; beim Durchsehen sind das bei neu graue Wände (Schwarzweiß-Bild), kein offener Rand.
- Zeit je Lauf (Median): alt 24 s, neu 10 s.

**Durchgesehen (Claude):** Vulkan und Kugel: alt bei links + unten deutlich hineingezoomt, neu richtig erweitert. Alt rechts zeigt bei zwei Bildern eine sichtbare senkrechte Naht im Himmel. Neu: einmal eine merkwürdige Hand im Schwarzweiß-Bild (rechts, Seed 11). Bewertung durch den User offen.
