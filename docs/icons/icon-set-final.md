# Funktions-Symbole: Bauanleitung

Stand 2026-10-27. Vom User gewählt, **eingebaut** (Branch `feat/function-icons`, in `next`); Symbol und Text stehen linksbündig wie in der Vorschau. Vorschau: `docs/icons/icon-set-final.png` (Kopie aus `data/`, dort von einem anderen Chat erstellt).

| Funktion (key) | Symbol | Vorschau-Name |
|---|---|---|
| Text to image (`txt2img`) | Rahmen mit „T“ | t2i A |
| Expand image (`outpaint`) | kleiner Rahmen in gestrichelter Fläche | expand A |
| Fill Selection (`inpaint`) | gestrichelte Auswahl mit Funken | fill B |
| Remove Selection (`remove`) | gestrichelte Auswahl mit X | remove B |
| Edit whole image (`edit`) | großer Funken mit zwei kleinen Plus | refine B |
| Multi Image Edit (`multi_edit`) | zwei gestapelte Bilder | multi A |
| Upscale (`upscale`) | kleines Quadrat, Pfeil zur großen Ecke | upscale A |
| Refine (`refine`) | Fokus-Ecken mit Kreis | refine A |

`img2img` (nur bei eigenem Workflow) hat kein Symbol gewählt: bleibt beim Platzhalter oder wird später entschieden.

## Einbau (wenn freigegeben)

1. Eigener Branch von `next`, z. B. `feat/function-icons`. (`feat/function-first` ist seit 27.10. in `next` gemergt: der Platzhalter, `icons.from_file` und `_function_icon` sind schon da.)
2. In `pccomfy/icons.py` die Hilfsfunktionen und Formen unten ergänzen. Achtung: Der Schlüssel `remove` ist dort schon das X der Entfernen-Knöpfe. Deshalb tragen die Funktions-Symbole den Präfix `fn-`.
3. `_function_icon` in `pccomfy/gui_theme.py`: statt `"placeholder"` die Form `f"fn-{key}"` nehmen, wenn es sie gibt. Eigene PNGs in `pccomfy/assets/functions/<key>.png` behalten Vorrang.
4. Test: Jeder Schlüssel aus `MODE_LABELS` (außer `img2img`) hat eine Form `fn-<key>`, `render` läuft für jede ohne Fehler.
5. Live prüfen: Fenster bei 100 % und 150 %, normal, gewählt (orange) und grau.

## Formen (24er-Raster, wie die übrigen Icons)

```python
def _dashed(x0, y0, x1, y1, dash=1.6, gap=4.4):
    """A dashed rectangle: solid corners, short dashes along the sides (a selection)."""
    c = 2.5
    out = [[(x0, y0 + c), (x0, y0), (x0 + c, y0)], [(x1 - c, y0), (x1, y0), (x1, y0 + c)],
           [(x1, y1 - c), (x1, y1), (x1 - c, y1)], [(x0 + c, y1), (x0, y1), (x0, y1 - c)]]
    for ax, ay, bx, by in [(x0 + c, y0, x1 - c, y0), (x1, y0 + c, x1, y1 - c), (x1 - c, y1, x0 + c, y1), (x0, y1 - c, x0, y0 + c)]:
        length = math.hypot(bx - ax, by - ay)
        n = max(1, round((length - gap) / (dash + gap)))
        step = (length - n * dash) / (n + 1)
        ux, uy = (bx - ax) / length, (by - ay) / length
        for i in range(n):
            s = step * (i + 1) + dash * i
            out.append([(ax + ux * s, ay + uy * s), (ax + ux * (s + dash), ay + uy * (s + dash))])
    return out


def _star(cx, cy, s, inner=0.28):
    """A four-pointed spark."""
    pts = [(cx + (s if i % 2 == 0 else s * inner) * math.cos(math.radians(-90 + i * 45)),
            cy + (s if i % 2 == 0 else s * inner) * math.sin(math.radians(-90 + i * 45))) for i in range(8)]
    return pts + pts[:1]


def _plus(cx, cy, s):
    return [[(cx - s, cy), (cx + s, cy)], [(cx, cy - s), (cx, cy + s)]]


_FOCUS = [[(3, 7), (3, 5)] + _arc(5, 5, 2, 180, 270) + [(7, 3)], [(17, 3)] + _arc(19, 5, 2, 270, 360) + [(21, 7)],
          [(21, 17)] + _arc(19, 19, 2, 0, 90) + [(17, 21)], [(7, 21)] + _arc(5, 19, 2, 90, 180) + [(3, 17)]]
SHAPES.update({
    "fn-txt2img": [_rrect(3, 3, 18, 18, 2), [(8, 8), (16, 8)], [(12, 8), (12, 17)]],
    "fn-outpaint": [_rrect(8, 8, 8, 8, 1.5)] + _dashed(2, 2, 22, 22),
    "fn-inpaint": _dashed(3, 3, 21, 21) + [_star(12, 12, 5)],
    "fn-remove": _dashed(3, 3, 21, 21) + [[(9, 9), (15, 15)], [(15, 9), (9, 15)]],
    "fn-edit": [_star(10, 13, 7.5, 0.25)] + _plus(19, 5, 2) + _plus(19.5, 18, 1.4),
    "fn-multi_edit": [[(18, 22), (4, 22)] + _arc(4, 20, 2, 90, 180) + [(2, 8)],
                      _rrect(6, 2, 16, 16, 2), [(22, 13), (18, 9), (9, 18)], _circle(11, 7, 1.6)],
    "fn-upscale": [_rrect(3, 13, 8, 8, 1.5), [(13, 11), (21, 3)], [(15, 3), (21, 3), (21, 9)],
                   [(3, 9), (3, 5)] + _arc(5, 5, 2, 180, 270) + [(9, 3)],
                   [(21, 15), (21, 19)] + _arc(19, 19, 2, 0, 90) + [(15, 21)]],
    "fn-refine": _FOCUS + [_circle(12, 12, 3)],
})
```

Herkunft der Formen (für den Kopfkommentar von `icons.py`): `multi_edit` folgt Lucide `images`, `upscale` Lucide `scaling`, `refine` Lucide `focus`, `edit` Lucide `sparkles` (ISC). Die übrigen sind eigene Formen im selben Stil.
