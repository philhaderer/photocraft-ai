# Testrunde: Krea 2 / MOSS Expand gegen die sichtbare Naht (Anleitung, 29.10.)

Warum: In der ersten Runde (`krea-moss-expand-ab.md`) passte der Inhalt mit einer Beschreibung der Umgebung, aber du hast 14 von 24 Bildern schlecht bewertet: fast überall eine sichtbare Kante oder Naht, oft ein Stil, der nicht passt, oder ein Helligkeitssprung. Diese Runde vergleicht vier Wege dagegen, mit **deinen eigenen Bildern**, und du bewertest **blind** (ohne zu wissen, welche Variante du siehst).

| Variante | Was anders ist |
|---|---|
| A | wie heute: der neue Rand greift 48 px ins Original |
| B | breit: 128 px, die weiche Kante ist entsprechend breiter |
| C | B + Seam-Korrektur (gleicht Helligkeit und Farbe an der Grenze an) |
| D | C + ein zweiter, schwacher Lauf (Denoise 0.4) nur über einen Streifen entlang der Grenze |

Jedes Bild bekommt vorher die Beschreibung seiner Umgebung (Qwen 3.5 9B, wie der Knopf „Describe“), dann zwei Ränder (rechts 35 %; links und unten je 25 %), mit Krea 2 und MOSS. Je Bild, Rand und Seed entstehen 8 Ergebnisse (2 Modelle × 4 Varianten).

## Vorbereitung (auf jedem Rechner)

1. Das Plugin ist aktuell: auf dem Hauptrechner von selbst; auf dem zweiten Rechner in GitHub Desktop „Fetch origin“, dann „Pull origin“.
2. ComfyUI läuft und hat diese Dateien: `krea2_turbo_int8_convrot.safetensors`, `qwen3vl_4b_fp8_scaled.safetensors` (Krea 2), `moss_image_sft_int8_convrot.safetensors`, `qwen3.5_9b_w4a8_gptq.safetensors`, `flux2-vae_small.safetensors`, die MOSS-LoRAs (`Moss\lora_dmd2.safetensors`, `Moss\lenovo_moss.safetensors`) und für die Beschreibung `qwen3.5_9b_int8_convrot.safetensors`. Fehlt etwas, zeigt das Zahnrad-Fenster des Plugins es mit Downloadlink.
3. Einen Ordner mit **4 bis 6 eigenen Bildern** anlegen (PNG, JPG oder WEBP), z. B. `C:\Testbilder\expand`. Gut sind verschiedene Arten: Landschaft, Innenraum, Porträt, Stadt, eine Grafik oder Illustration, ein Bild mit klaren Linien (Horizont, Wand, Boden). Große Bilder werden auf 1280 px verkleinert.

## Starten

Im Plugin-Ordner in die Adresszeile des Explorers `powershell` tippen, Enter, dann:

```
.venv\Scripts\python.exe tests\live_expand_seam.py run --images "C:\Testbilder\expand"
```

Dauer: etwa 2 bis 2,5 Minuten je Bild (5 Bilder: ca. 12 Minuten). Mit `--seeds 2` gibt es jedes Bild mit zwei Seeds (doppelt so viele Bilder, doppelte Zeit). Der Rechner ist in der Zeit mit der GPU beschäftigt. Am Ende steht „DONE … pictures in data\expand-seam-test\<Zeit>“.

## Bewerten

```
.venv\Scripts\python.exe tests\live_expand_seam.py rate
```

Das Fenster ist wie in der ersten Runde, nur ohne Modell und Variante im Titel („Bild 7/40“), in zufälliger Reihenfolge:

- **1 / 2 / 3** = gut / mittel / schlecht, **← / →** blättern, **G** zeigt die Grenze zum Original als orangen Rahmen.
- Gründe ankreuzen, eine Notiz, wenn nötig. Alles wird sofort gespeichert; schließen und später weitermachen geht (es startet beim ersten unbewerteten Bild).

## Auswerten und zurückgeben

```
.venv\Scripts\python.exe tests\live_expand_seam.py summary
```

zeigt die Tabelle je Modell und Variante und schreibt sie nach `ergebnis.md` im Ordner der Runde.

- **Hauptrechner:** einfach „Fertig“ sagen; ich lese den Ordner selbst.
- **Zweiter Rechner:** aus `data\expand-seam-test\<Zeit>\` die Dateien `key.json`, `bewertung.json` und `ergebnis.md` mitbringen (USB-Stick, Mail an dich selbst) und in den Chat ziehen oder in denselben Ordner auf dem Hauptrechner legen. Die Bilder selbst brauche ich nur, wenn wir uns einzelne ansehen wollen. Auf dem zweiten Rechner nichts committen oder hochladen.

Danach entscheiden wir: eine Variante einbauen, oder Expand bei Krea 2 / MOSS abschalten.
