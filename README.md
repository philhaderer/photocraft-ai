# PhotoCraft AI

AI functions for [PhotoCraft](https://github.com/storytold/photocraft) on Windows: Fill, Remove, Expand, Edit,
Multi Image Edit, Upscale, Refine and Text to image. Everything runs locally in
[ComfyUI](https://github.com/comfyanonymous/ComfyUI) on your own graphics card. Each result lands in your document as a
**new layer with an editable layer mask**.

> Unofficial community project, not affiliated with PhotoCraft, ArtCraft or Storyteller. PhotoCraft is in early alpha
> and so is this plugin. "PhotoCraft AI" is a working title.

## Quick start

1. **Get the parts**: Windows 10/11 with an NVIDIA card (16 GB VRAM), [Python 3.11+](https://www.python.org/downloads/windows/)
   (tick "tcl/tk" and "Add python.exe to PATH"), PhotoCraft 0.16 or 0.17 (portable) and ComfyUI 0.42 or newer.
2. **Install the plugin**: *Code › Download ZIP*, unpack it, double-click **`setup-windows.bat`**. It also creates the
   desktop shortcut **PhotoCraft AI** (it looks for `photocraft.exe` itself and asks once if it can't find it).
3. **Get the models**: start ComfyUI, then open the plugin's gear window. Under **Easy Mode** one button downloads the
   two starter models (Flux 3 and Fibo, about 20 GB), which cover all functions. Restart ComfyUI afterwards.
4. Double-click **PhotoCraft AI** on your desktop (ComfyUI running, PhotoCraft closed).
5. In the plugin window switch on **Easy Mode**, pick a function, type a prompt, press **Generate** (Ctrl+Enter).

Easy Mode shows only the function buttons and the prompt; the plugin picks the best installed model and its tested
settings. Switch it off for all settings.

## What it does

A small window sits next to PhotoCraft. You pick a **function** at the top, a **model** below it, type a prompt and
press **Generate**. The plugin sends the picture (or the selection) to ComfyUI and puts the result back into
PhotoCraft as a new layer in a group, with a soft layer mask where that makes sense.

| Function | What it does |
|---|---|
| **Fill Selection** | Select an area, type what should appear there. |
| **Remove Selection** | Select an object (the whole object inside); it is removed and the background filled in. |
| **Expand image** | Extend the canvas with the Crop tool, fill the new area white; the plugin paints it. |
| **Edit whole image** | Changes the whole picture from your text ("make it night"). |
| **Multi Image Edit** | Edits the picture with reference images (drop, paste or add files into the slots). |
| **Upscale (new file)** | Enlarges the picture or selection into a new document, up to 24 MP. |
| **Refine (same size)** | Cleans up the picture or selection at the same size, as a new layer. |
| **Text to image** | A new picture from text only, as a new layer. |

Which model offers which function:

| | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Fill Selection | | | ✓ | ✓ | | |
| Remove Selection | ✓ | ✓ | ✓ | ✓ | | |
| Expand image | ✓ | ✓ | ✓ | ✓ | | |
| Edit whole image | ✓ | ✓ | ✓ | ✓ | | |
| Multi Image Edit | ✓ | ✓ | ✓ | ✓ | | |
| Upscale | ✓ | ✓ | | | | |
| Refine | | ✓ | | ✓ | | |
| Text to image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Models you don't have are greyed out. The tooltip of each function shows which models work best for it.

More in the window: **variants** (several results as layers in one group), **edge feather, context, mask density,
sharpen and match colours** in the advanced settings, **Undo / Redo** of a whole run, presets and custom LoRAs.

## Install

You need the plugin, PhotoCraft, ComfyUI and the model files. Details for each step:

1. **Plugin**: *Code › Download ZIP* and unpack it (e.g. to `C:\programs\photocraft-ai`), or `git clone` it. Install
   Python, then double-click **`setup-windows.bat`**; it creates `.venv`, installs what the plugin needs and ends with
   "Setup done".
2. **ComfyUI** (0.42.0 or newer, running on `http://127.0.0.1:8188`). For Upscale and Refine also install
   [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) 2.13.0 or newer (ComfyUI-Manager). All other nodes
   are part of ComfyUI.
3. **Model files**: use the download buttons in the gear window, or see [Models](#models). ComfyUI reads its model
   folders only at start, so restart it after adding files.
4. **Desktop shortcut**: `setup-windows.bat` creates it for you. If it could not find `photocraft.exe`, it asks for it
   once. To redo it later, run this in the plugin folder (type `powershell` into Explorer's address bar):

   ```
   .venv\Scripts\python.exe -m pccomfy shortcut
   ```

   Add `--photocraft "C:\programs\photocraft\photocraft.exe"` to name the file yourself. If `setup-windows.bat` said it uses
   Python directly, use the path in `data\python.txt` instead of `.venv\Scripts\python.exe`.
5. **First start**: ComfyUI is running, PhotoCraft is closed. Double-click **PhotoCraft AI** on the desktop. PhotoCraft starts, and a
   few seconds later the plugin window appears. In the gear window, red entries are model files that are still missing.

The shortcut starts PhotoCraft with its control channel (loopback only, token-protected, file access limited to
`data\exchange`) and then the plugin, without a console window. To update: download the new version (or `git pull`)
and restart. Your settings stay in `data\`.

## Models

You only need the files for the models you want; the plugin enables what it finds. All download links, sizes, target
folders and licences are in [docs/model-downloads.md](docs/model-downloads.md).

- Release 1 uses the **int8 ConvRot** files, which fit into 16 GB VRAM.
- Some files are **gated**: log in to Hugging Face and accept the licence on the model page first, otherwise the
  download answers "401".
- If you keep models outside ComfyUI, set them up in ComfyUI's `extra_model_paths.yaml`.

## Tips

- **Fill Selection**: describe what should appear, e.g. "a wooden bench". Hide the layers of earlier results before
  running again.
- **Remove Selection**: select the whole object with a little margin. If the first try didn't work, remove it again.
- **Expand image**: enlarge the canvas with the Crop tool (Enter) and fill the new area white. An empty prompt often
  works best. Expand large areas in small steps.
- **Edit whole image** and **Multi Image Edit** change the whole picture; a selection is ignored. In Multi Image Edit,
  name the reference images in your text by the tags shown on their slots.
- **Upscale / Refine**: add a short description of your image in front of the default text.
- Ctrl+Z / Ctrl+Y in PhotoCraft work as usual; the plugin's own Undo / Redo buttons undo a whole run.

## Known limitations

- Only tested on Windows with a 16 GB NVIDIA card.
- During a run, PhotoCraft briefly opens a temporary document, so tabs flicker. Don't switch documents or change the
  selection while a run is going.
- A run consists of several PhotoCraft steps (history entries).
- CMYK, Lab and 16-bit documents go through 8-bit RGB.

## Licences of the models

The plugin's code is MIT / Apache-2.0, but **the models have their own licences**, and some are **non-commercial
only**: Fibo 2.0 (CC BY-NC 4.0) and the FLUX.2 Klein files. Others ask for credit (the Lenovo UltraReal LoRA for MOSS:
Danrisi). Check [docs/model-downloads.md](docs/model-downloads.md) before you use results commercially.

## For developers

- **Your own workflows**: export a ComfyUI workflow in API format into `workflows\` and give the nodes the plugin should
  fill a title: `pc:image`, `pc:mask`, `pc:prompt`, `pc:negative`, `pc:sampler`, `pc:size` / `pc:latent`, `pc:output`
  (more in [pccomfy/workflows.py](pccomfy/workflows.py)).
- **Command line**: `python -m pccomfy check` (tests both connections), `python -m pccomfy run <mode> -p "…"`,
  `python -m pccomfy --help`.
- **Tests**: `python tests/run_all.py` (stubbed Tk, fake PhotoCraft and fake ComfyUI; no GPU needed).
- **Diagnostics**: `data\exchange\last-graph.json` (last graph sent) and `data\exchange\runs.jsonl` (one line per run).

## Credits

- [PhotoCraft](https://github.com/storytold/photocraft) by the ArtCraft team
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and the Comfy-Org model repositories
- [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) (Upscale and Refine)
- [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek, the starting
  point of this project (MIT / Apache-2.0)
- The model authors: Black Forest Labs (FLUX.2 / FLUX.3 Klein), Qwen (Qwen-Image 2.1), Bria (Fibo 2.0), Krea (Krea 2),
  MOSS-Image, ByteDance (SeedVR2), obsxrver (FLUX.2 Klein int8 ConvRot), lodestones (MOSS DMD2 LoRA), Danrisi (Lenovo
  UltraReal LoRA), vizsumit (UltraReal LoRA for Flux 2)
- [Lucide](https://lucide.dev) (ISC): the window's icons follow its shapes and style
- [Inter](https://rsms.me/inter/) font by Rasmus Andersson (SIL Open Font License 1.1, see `OFL-Inter.txt`)

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option. The models are not part of this
repository and have their own licences (see above).
