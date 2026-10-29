# Krea 2 / MOSS Expand: leerer Prompt gegen Beschreibung (A/B-Test 29.10.)

Anlass: Krea 2 und MOSS sind Masken-Modelle. Bei Expand bekamen sie einen leeren Prompt und malten Fremdes in den neuen Rand (Balkon neben dem Rüstungssaal; PLAN E3). Entscheidung des Users (29.10.): Option C, ein Knopf „Describe“, der eine Beschreibung ins Prompt-Feld schreibt; bei diesen Modellen klar sagen, dass der Prompt nötig ist; sind die Ergebnisse nicht gut, wird Expand bei ihnen wieder abgeschaltet. Vorher dieser Test.

Aufbau: der Expand-Weg des Plugins direkt gegen ComfyUI nachgebaut (ohne PhotoCraft): Rand transparent, `imaging.outpaint_mask` (Überlappung 48 px), Context 0.4, Base res. 1024 (Krea) / 1216 (MOSS), Mask grow/blur 8, die Workflows `krea2-turbo-inpaint.json` und `moss-image-inpaint.json` mit Turbo/DMD2. Drei Bilder (Nachthaus, Fuchs im Winterwald, Porträt im Raum) × zwei Ränder (rechts 35 %; links + unten je 25 %) × zwei Seeds × drei Prompts × zwei Modelle = 72 Bilder. Beschrieben hat Qwen 3.5 9B (`describe-image.json`) das Original ohne Rand, ca. 2 s je Beschreibung (die erste 6 s, Laden). Ein Lauf: Krea 2 im Mittel 6,8 s, MOSS 7,5 s.

Prompts:
- **leer** (bisher)
- **allgemein**: „Describe this picture in one or two sentences: what it shows, the setting, the style and the light.“
- **nur Umgebung**: „Describe only the setting and the background of this picture in one sentence: the place, the surfaces, the style and the light. Do not mention the main subject (people, animals or the central object).“

Bewertet durch Ansehen (Claude), je 24 Bilder pro Prompt:

| Prompt | passt zur Szene | Fremdes im Rand | Hauptmotiv doppelt |
|---|---|---|---|
| leer | ca. 2 | ca. 22 (Personen, Auto, Katze, Bräutigam, Radfahrer, Stadt, See mit Bergen, Möbel, Lagerfeuer) | – |
| allgemein | ca. 12 | – | ca. 12 (zweites Haus, zweiter Fuchs, zweiter Mann, Spiegelung des Hauses) |
| nur Umgebung | ca. 24 | – | – (einmal eine dritte Laterne, passt zur Szene) |

Befunde:
- Ohne Prompt sind beide Modelle für Expand unbrauchbar. Mit der Beschreibung **nur der Umgebung** setzen beide die Szene in allen 24 Bildern plausibel fort (Wald, Feld, Raum mit Holz und Fenster), Krea 2 und MOSS etwa gleich gut.
- Nennt die Beschreibung das Hauptmotiv, malen beide es in etwa der Hälfte der Fälle ein zweites Mal (wie Fibo mit eingetippter Beschreibung, `fibo-expand-ab.md`).
- Bei einigen Bildern bleibt ein sichtbarer Helligkeitssprung an der Grenze zum Original (Nachthaus links + unten, Porträt rechts bei Krea 2); das ist ein Fall für die Seam-Korrektur (E2).

Bilder und Skript: `data/ab-expand-krea-moss/20261029/` (lokal, nicht im Repo): `sheet_<modell>_<bild>_<rand>.png` (Zeilen = Prompt, Spalten = Seed), `descriptions.json`, `runs.json`, `expand_ab.py`.

Folgerung für Option C: der Knopf „Describe“ fragt nach der Umgebung ohne Hauptmotiv (der dritte Prompt). Expand bleibt bei Krea 2 und MOSS an, aber nur mit Prompt.
