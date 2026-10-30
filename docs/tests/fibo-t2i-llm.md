# Fibo Text to image: mit und ohne LLM (Blindtest 30.10.)

Runde `data/fibo-llm-test/20261030-122255` (`tests/live_fibo_llm.py`): 12 Prompts aus `testprompts.md` (Schrift, Zählen,
Position, Gesichter, Bewegung, Farben, Layout) × 2 Seeds, 1216 px, Startwerte von Fibo Text to image. Mit LLM schreibt
Qwen 3.5 9B (int8 ConvRot) mit Brias „Generate“-Systemprompt den JSON-Prompt; etwa 20 s mehr je Bild.

| ohne LLM besser | mit LLM besser | gleich gut | beide schlecht |
|---|---|---|---|
| 9 | 4 | 11 | 0 |

- Ohne LLM klar besser bei Zählen (40), Position (55) und Makro (143), je 2 von 2.
- Mit LLM je einmal besser bei Schrift (1), Katze (25), Tänzerin (90) und Magazin-Layout (180).
- Der User: schwer zu entscheiden.

**Entscheidung (User 30.10.):** Der Haken „LLM prompt enhancement“ startet bei Fibo Text to image **aus**, bleibt aber verfügbar.
