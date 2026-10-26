# Fragen an dich (Lane L1), Runde 2

Antworten bitte in `ANTWORTEN.md` (Nummer und Buchstabe, z. B. „1 A"). Ohne Antwort gilt die Empfehlung.
Fertig und getestet ist schon: kein Modell beim allerersten Start; beim nächsten Start ist das zuletzt gewählte Modell wieder da; ist es inzwischen nicht mehr verfügbar, ist kein Tab gewählt. Es fehlt nur, **wie das Fenster in diesen Zuständen aussieht**.

## 1. Kein Modell gewählt (es gibt Modelle): was steht im Fenster?
Gemeint: erster Start, oder das letzte Modell ist weg. Parameter, Regler, Modi und der Prompt sind dann nicht sichtbar.
- **A (Empfehlung):** oben die Tab-Knöpfe, darunter ein ruhiger Satz **„Choose a model"**, unten die Zeile mit den Verbindungspunkten, Refresh, Reset und dem Zahnrad. Ohne Generate-Knopf. Das Fenster ist dadurch ganz klein.
- B: wie A, aber der Generate-Knopf bleibt sichtbar und ist ausgegraut (man sieht, wo er später sitzt).
- C: wie A, aber unter dem Satz steht pro Modell eine Zeile mit der Kurzbeschreibung (dieselben Texte wie beim Darüberfahren der Tabs). Gut für Neue, das Fenster ist höher.

## 2. Kein einziges Modell gefunden (frische Installation): was steht im Fenster?
- **A (Empfehlung, so wie du es geschrieben hast):** nur der Satz **„Link your model in the settings"** und das Zahnrad (Tabs, Parameter, Generate weg).
- B: wie A, dazu ein Knopf „Open settings", der das Einstellungs-Fenster öffnet (du musst das Zahnrad nicht suchen).
- C: die Tabs bleiben sichtbar (alle rot) und darunter der Satz. Ein Klick auf einen Tab öffnet die Einstellungen bei diesem Modell.

## 3. Titelleiste: soll sie auch dunkler werden?
Die Titelleiste des Plugin-Fensters (oben, mit dem Namen) hat noch den alten Grauton `#404040`. Alles andere ist jetzt `#282828`.
- **A (Empfehlung):** Titelleiste bleibt, wie sie ist (passt zur PhotoCraft-Leiste, die du bewusst nachgemessen hast).
- B: Titelleiste auch `#282828`. Das ist eine Zeile in `gui.py` (außerhalb des erlaubten Bereichs, deshalb frage ich).

## 4. Meldung, wenn das letzte Modell fehlt
Beim Start steht dann unten: „Krea 2 Turbo is not available (model files missing). Choose a model." (englisch, wie der Rest).
- **A (Empfehlung):** so lassen.
- B: du gibst mir andere Wörter.
