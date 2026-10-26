# Fragen an dich (Lane L1)

Antworten bitte in `ANTWORTEN.md`, einfach Nummer und Buchstabe (z. B. „1 A"). Bei „keine Antwort" bleibt die Empfehlung.
Bis dahin ist alles so gebaut wie unter „jetzt".

## 1. Wo erscheint das Einstellungs-Fenster?
Das Zahnrad rechts neben den Tabs öffnet die Einstellungen (welche Modell-Dateien da sind, Download-Links, Dateien mit anderem Namen verknüpfen, Danksagungen).
- **A (Empfehlung, jetzt so):** ein eigenes kleines Fenster neben dem Hauptfenster. Das Hauptfenster bleibt schmal.
- B: die Einstellungen ersetzen im Hauptfenster kurz den Inhalt, mit „Zurück"-Knopf. Aufwendiger, nichts liegt daneben.
Warum Frage: du siehst es; ich kann nicht testen, ob das Zusatzfenster bei dir vor PhotoCraft sichtbar bleibt.

## 2. Was passiert beim Klick auf einen grauen Tab (Modell fehlt)?
- **A (Empfehlung, jetzt so):** der Tab wechselt nicht, die Einstellungen öffnen sich bei diesem Modell.
- B: der Tab wechselt trotzdem, und beim Generieren kommt die Meldung, was fehlt.
- C: nur der Hinweis beim Darüberfahren (Tooltip), kein Klick-Verhalten.

## 3. Und wenn ein gespeichertes Preset ein Modell mit fehlenden Dateien braucht?
- **A (Empfehlung):** das Preset lädt nur für den Teil, der geht, und die Meldung sagt, was fehlt. Braucht eine kleine Änderung in einer Datei, die nicht L1 gehört (Haupt-Chat oder L3).
- B (jetzt so): das Preset öffnet die Einstellungen und der vorherige Tab bleibt stehen.

## 4. Wörter in den Meldungen
Die Texte sind Englisch, wie der Rest des Fensters. Beispiel: „Krea 2 Turbo: missing: qwen_image_vae.safetensors -> ComfyUI\models\vae. Restart ComfyUI after copying files." und im Tooltip „Set in settings (gear)."
- **A (Empfehlung):** so lassen.
- B: du gibst mir bessere Wörter.

## 5. Dateien per Ziehen und Ablegen auf das Einstellungs-Fenster (yaml)
Das braucht ein Zusatzprogramm (`tkinterdnd2`, eine neue Abhängigkeit). Es steht auch für die Referenzbild-Felder in L2 an.
- **A (Empfehlung):** erst mit dem normalen „Datei wählen"-Knopf (ist schon da), Ziehen und Ablegen kommt gemeinsam mit L2, wenn du `tkinterdnd2` ausprobiert hast.
- B: ich baue Ziehen und Ablegen jetzt ein, du musst `tkinterdnd2` vorher installieren und freigeben.
