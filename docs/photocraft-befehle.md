# PhotoCraft-Befehle (PLAN D.6 / OpenFill T1): Prüfung, nichts gebaut

Stand 2026-10-27. Quelle: die Befehlsliste der Engine (`photocraft-cli commands --json`) von **0.15.1** (935 Befehle) und **0.16.0** (940), dazu ein Kopflos-Lauf (`photocraft-cli run --new …`) mit Crop über den Rand, Feather, Gruppe und einem unbekannten Parameter, in beiden Versionen gleich ausgegangen. Das laufende PhotoCraft-Fenster wurde nicht benutzt.

## Tabelle

| Befehl | 0.15.1 | 0.16 | Nutzen wir schon? | Folge für uns |
|---|---|---|---|---|
| `select.modify.feather` `{radius 0.1..1000}` | ja | ja | nein | **Feather-Vorschau möglich:** die Auswahl in PhotoCraft weich machen, damit man die Kante vor dem Lauf sieht (offener Befund 4 erledigt: der Name stimmt). Im Kopflos-Test lief er. |
| `select.modify.expand` / `contract` `{radius 1..500}` | ja | ja | nein | Auswahl vor dem Lauf vergrößern/verkleinern, z. B. für Remove (Objekt ganz drin). |
| `select.saveSelection` / `select.loadSelection` | ja | ja | nein | Auswahl als Kanal sichern und nach dem Lauf wiederherstellen (heute: `select.reselect`). Nur nötig, wenn Feather/Expand die Auswahl des Nutzers verändern. |
| `layer.layerMask.revealSelection` | ja | ja | nein (wir: `revealAll` + Maske einfügen) | Ebenenmaske direkt aus der Auswahl; einfacher für Layer mask „hard“. Für „soft“ bleibt unser eigenes Einfügen der Maske. |
| `layer.new.group` `{name}` | ja | ja | nein | **Gruppe für Varianten möglich** (Kopflos-Test: neue Gruppe, Ebenen-ID kommt zurück). Ebenen hinein mit `layer.moveTo {position: "into"}` (mehrere in einem Undo-Schritt) oder `layer.new.groupFromLayers`. |
| `history.newSnapshot` / `selectSnapshot` / `deleteSnapshot` | ja | ja | **ja** (Undo/Redo-Knöpfe) | Ein Schnappschuss ist eine benannte Kopie, **kein Verlaufsschritt**; `selectSnapshot` springt in *einem* neuen Schritt zurück. So arbeiten unsere Undo-Knöpfe schon. |
| mehrere Schritte = **ein Strg+Z** | nein | nein | – | Es gibt keinen Befehl, der Schritte bündelt (gesucht nach transaction/suspend/one undo). Strg+Z in PhotoCraft geht nach einem Lauf weiter Schritt für Schritt (Einfügen, Maske, Name). Bleibt so; der Undo-Knopf des Plugins ist der „eine Schritt“. |
| `history.selectState` / `history.deleteState` | ja | ja | nein | Zurück zu einem Verlaufsschritt in einem Schritt bzw. Schritte löschen. Möglicher Ersatz für Snapshots, aber riskanter (Index verschiebt sich, wenn der Nutzer zwischendurch arbeitet). Nicht empfohlen. |
| `image.crop` mit Rechteck **über den Rand** | ja | ja | nein (wir: `image.canvasSize`) | **Geht in beiden** (Kopflos-Test: 200×200 → 300×240 bei x −50, y −20). Damit ließe sich Expand ohne den Umweg „Crop-Werkzeug + Enter + weiß füllen“ vorbereiten (offener Befund 3). `contentAware` füllt die neue Fläche, wenn gewünscht. |
| `channel.duplicate` | ja | ja | nein | Maske/Auswahl als Kanal kopieren; nur für saveSelection-Ideen nötig. |
| `layer.copyToDocument` `{document, layers, at, offset}` | ja | ja | nein (wir: Ergebnis-PNG öffnen, `select.all` + `edit.copy`, schließen, `edit.paste`) | Ebenen direkt zwischen Dokumenten kopieren, ohne PhotoCrafts Zwischenablage. Vorteil: Ein Lauf überschreibt nicht mehr, was der Nutzer selbst kopiert hat, und es sind weniger Schritte. Masken-Einfügen (`target: "mask"`) bräuchte weiter `edit.paste`. |
| `edit.paste` | ja | ja, **neuer Parameter** | **ja** | 0.16: `clampToCanvas` (Standard **an**: das Eingefügte bleibt auf der Leinwand, ist es größer, oben links). Wir geben `center` mit und fügen nie Größeres ein: heute ohne Folge. Unbekannte Parameter nimmt 0.15.1 stillschweigend an (getestet), also könnten wir `clampToCanvas: false` für beide setzen, falls nötig. |

## 0.15.1 → 0.16

- Neu in 0.16: `help.checkForUpdates`, `updates.status`, `style.presets.exportAsl`/`importAsl`, `type.fillPath`. Keiner davon betrifft uns.
- Weg: keiner. Von den Befehlen, die wir benutzen, fehlt in keiner Version einer; geändert hat sich nur `edit.paste` (siehe oben).
- Beim Umstieg auf 0.16 bleibt also noch: einmal den Start über `photocraft-ai 0.16.bat` und einen Lauf je Funktion live prüfen (Steuerport, `ui.inspect`/`session.inspect`).

## Was daraus wurde (Entscheidung des Users, 27.10.)

Gebaut: 1 (Feather-Vorschau, als Quick Mask), 2 (Gruppe, Name „<Funktion> <Lauf-Nr.>“) und 4 (ohne Zwischenablage). Abgelehnt: 3 (Expand bleibt wie bisher). Befunde beim Bauen, in 0.15.1 und 0.16 gleich:

- `layer.copyToDocument` macht das **Ziel** zum aktiven Dokument; vor dem Schließen der Ergebnis-PNG muss sie wieder aktiviert werden, sonst schließt man das Bild des Nutzers. Die Kopie landet als Pixel-Ebene über der aktiven (auch über einer Einstellungsebene) und wird aktiv; `offset` setzt sie pixelgenau.
- Ist eine **Gruppe** aktiv, landet die Kopie **in** der Gruppe. Das Plugin schiebt das Ergebnis dann mit `layer.moveTo {position: "above"}` über die Gruppe.
- `layer.layerMask.revealSelection` verbraucht die Auswahl (danach keine Auswahl). Die weiche Maske geht über `select.loadSelection {channel: "transparency"}` einer Hilfsebene: auf den Grauwert genau.
- Quick Mask an: `document.inspect` meldet keine Auswahl; aus: die Auswahl ist wieder da.

## Was daraus werden kann (Vorschläge, Entscheidung des Users)

1. **Feather-Vorschau** (E.9 Ränder): Schalter oder Knopf „Show feather“, der die Auswahl in PhotoCraft per `select.modify.feather` weich macht. Vorher die Auswahl mit `saveSelection` sichern, danach mit `loadSelection` zurückholen.
2. **Varianten in einer Gruppe:** bei mehr als einer Variante eine Gruppe „<Funktion> <Nr.>“ anlegen und die Ergebnisse hineinlegen.
3. **Expand per Crop:** statt des Hinweises „Crop-Werkzeug, Enter, weiß füllen“ könnte das Plugin die Fläche selbst erweitern (Seiten und Pixel im Plugin wählen). Größere Änderung, eigene Entscheidung.
4. **Ergebnis ohne Zwischenablage** über `layer.copyToDocument`: die PhotoCraft-Zwischenablage des Nutzers bleibt unberührt. Klein, aber es berührt das Einfügen jedes Laufs: nur mit Live-Test aller Funktionen.
