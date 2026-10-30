# OpenFill-Modell-Manager im Vergleich (Punkt 14, T4; 30.10.)

Quelle: `C:\programs\openfill` (Klon von github.com/beckettharriman/openfill, Apache-2.0, Stand 84f904d). Gelesen: `docs/models.md`, `gimp-openfill/openfill/hardware.py`, `local_models.py`, `downloads.py`. Kein Code übernommen, nur Ideen.

## Gegenüberstellung

| Thema | OpenFill | Wir heute | Empfehlung |
|---|---|---|---|
| Hardware erkennen | `hardware.py`: Grafikkarte und VRAM über nvidia-smi, NVML, DXGI/Registry, ComfyUI `/system_stats`; dazu RAM und freier Platz | nichts (Release 1 nur 16 GB) | **anpassen:** VRAM aus ComfyUI `/system_stats` (geht schon über `comfy.system_stats`), RAM und Platz aus Windows; kein eigener Treiber-Code |
| „Passt auf diesen PC“ | `hardware.fit`: VRAM ≥ Gewichte + Arbeitsspeicher (1,5 bis 2,5 GB) = „läuft gut“; darunter bis zu einer Untergrenze je Familie = „läuft langsamer (Systemspeicher)“; sonst „zu groß“; Zahlen im Tooltip | nichts | **übernehmen** als Knopf mit der VRAM-Größe im Zahnrad (deine Idee); Werte außer 16 GB als „geschätzt“ kennzeichnen |
| Eigene Dateien finden | `local_models.py`: liest nur den Kopf von `.safetensors`/`.gguf` und erkennt die Familie an typischen Tensoren; nie Pickle-Dateien öffnen | Name, Groß/Klein, `\`/`/`, Aliasse, bloßer Dateiname in einem anderen Unterordner; „Choose another file…“ zum Verknüpfen; `extra_model_paths.yaml` für „liegt da, ComfyUI neu starten“ | **übernehmen (Kopf lesen)**, um umbenannte Dateien als Vorschlag zum Verknüpfen anzubieten |
| GGUF | eigener Loader (ComfyUI-GGUF) je Familie | Workflows laden nur mit `UNETLoader`; GGUF-Dateien sieht das Plugin nicht; ComfyUI-GGUF ist bei dir nicht installiert | **später** (8-GB-Nutzer, nach Release 1): Loader im Graph tauschen + Knoten-Paket als Abhängigkeit |
| Download | `downloads.py`: `.part`-Datei, Fortsetzen (HTTP Range), Größe und SHA-256 prüfen, erst dann umbenennen; Platz vorher prüfen; Abbrechen | nur Links und Größen im Manifest | **übernehmen** für „Download all missing“ je Modell; SHA-256 ins Manifest |
| Hugging-Face-Login (gesperrte Dateien) | Feld nur im Download-Panel, 4 Schritte (Seite öffnen, Lizenz annehmen, Token anlegen, einfügen); Token nur an huggingface.co, nicht bei Weiterleitungen, nie im Log | Hinweis „gated“ im Manifest | **übernehmen** (betrifft Flux 3 Klein und den Upsampler) |
| Lizenz je Modell | Link „Read the license“ im Menü | Lizenz als Text in der Notiz | **übernehmen** als Link |
| Live-Suche Hugging Face / Civitai, Rangliste | ja (`hub.py`, `rank_score`) | feste, geprüfte Liste | **weglassen** (unsere Workflows passen nur zu bestimmten Dateien) |
| Fehlertexte mit nächstem Schritt | `ui_text.py` | teilweise (Preflight-Zeilen) | **anpassen**, wenn wir den Download bauen |

## Befunde zu deinen Punkten

- **Bug „New file“:** `ui_settings._link_expected_picked` setzt den erwarteten Namen immer als erste Zeile ein (damit man eine Verknüpfung wieder lösen kann), auch wenn die Datei gar nicht da ist.
- **Wie die Suche heute geht:** ComfyUI meldet über `/object_info` die Listen von `UNETLoader` (Ordner `diffusion_models` und `unet`), `CLIPLoader` (`text_encoders`, `clip`), `VAELoader` und `LoraLoaderModelOnly`; das Plugin sucht darin den erwarteten Namen (`inventory.resolve`). Ordner aus `extra_model_paths.yaml` werden zusätzlich direkt durchsucht, nur um „neu starten“ von „fehlt“ zu unterscheiden. ComfyUI liest seine Ordner nur beim Start.
- **Fehlende LoRAs und Dateien im Manifest:** `Flux 3\flux-3-image-klein-restore.safetensors` (Flux 3 Upscale, Stärke 0,5, an; lädt über den AusBoss-LoRA-Lader mit einer JSON-Liste, deshalb übersieht der Test ihn) und `birefnet.safetensors` (Hintergrund weg bei den Slots). Quelle der Restore-LoRA: `ausboss/FLUX-3-Image-Klein-Restore-LoRA`.
- **Deine Regel „was die Startwerte brauchen, ist Pflicht“:** Qwen Text to image startet mit Enhance an, `qwen3.5_9b_w4a8_gptq` steht aber nur als optional. Die übrigen optionalen Dateien (Turbo-LoRA, DMD2, Lenovo, Upsampler, TAESD) einzeln gegen die Startwerte prüfen.
- **Zwei Qwen3-VL-8B-Dateien bei Qwen 2.1:** Der Edit-Workflow (Edit, Fill, Expand, Remove, Multi Image Edit) lädt `qwen3vl_8b_fp8_scaled` (10,6 GB), Text to image `qwen3vl_8b_int8_convrot` (9,4 GB). Dasselbe Modell in zwei Formaten. Wenn ein A/B-Test gleich gut ausfällt, braucht Qwen nur noch die ConvRot-Datei.
- **VRAM-Recherche:** Es gibt keine offiziellen VRAM-Angaben für die int8-ConvRot-Dateien bei 8 oder 12 GB. ComfyUI lagert mit „Dynamic VRAM“ selbst in den Systemspeicher aus. Ein Test mit Krea 2 auf 12 GB zeigt: Spitzen von 11–12 GB, int8 spart vor allem System-RAM. int8 braucht eine Grafikkarte ab Turing (SM 7.5). Belastbar sind also nur eigene Messungen.
