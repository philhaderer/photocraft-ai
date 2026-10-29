# PhotoCraft AI

AI functions for [PhotoCraft](https://github.com/storytold/photocraft) on Windows: Fill, Remove, Expand, Edit,
Multi Image Edit, Upscale, Refine and Text to image. Everything is computed locally by
[ComfyUI](https://github.com/comfyanonymous/ComfyUI) on your own graphics card. Each result lands in your document as a
**new layer with an editable layer mask**.

![Before / after: Fill Selection in PhotoCraft](docs/before-after.jpg)

> Unofficial community project, not affiliated with PhotoCraft, ArtCraft or Storyteller. PhotoCraft is in early alpha
> and so is this plugin. "PhotoCraft AI" is a working title.
>
> Based on [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek
> (see [Based on](#based-on)).

## What it does

A small window sits next to PhotoCraft. You pick a **function** at the top, a **model** below it, type a prompt and
press **Generate** (Ctrl+Enter). The plugin sends the picture (or the selection) to ComfyUI and puts the result back
into PhotoCraft as a new layer in a group, with a soft layer mask where that makes sense.

| Function | What it does |
|---|---|
| **Fill Selection** | Select an area, type what should appear there. |
| **Remove Selection** | Select an object (the whole object inside); it is removed and the background filled in. |
| **Expand image** | Extend the canvas with the Crop tool, fill the new area white; the plugin paints it. |
| **Edit whole image** | Changes the whole picture from your text ("make it night"). |
| **Multi Image Edit** | Edits the picture with up to several reference images (drop, paste or add files into the slots). |
| **Upscale (new file)** | Enlarges the picture or selection into a new document, up to 24 MP. |
| **Refine (same size)** | Cleans up the picture or selection at the same size, as a new layer. |
| **Text to image** | A new picture from text only, as a new layer. |

Which model offers which function:

| | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Fill Selection | | | ✓ | ✓ | | |
| Remove Selection | ✓ | ✓ | ✓ | ✓ | | |
| Expand image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Edit whole image | ✓ | ✓ | ✓ | ✓ | | |
| Multi Image Edit | ✓ | ✓ | ✓ | ✓ | | |
| Upscale | ✓ | ✓ | | | | |
| Refine | | ✓ | | ✓ | | |
| Text to image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Models you don't have are greyed out. The tooltip of each function shows which models work best for it.

More in the window:

- **Variants**: several results become several layers in one group; the first is visible.
- **Edge feather, Context, Mask density, Sharpen, Match colours** in the advanced settings, with a **Show feather**
  preview of the soft edge in PhotoCraft.
- **Undo / Redo** of a whole run, presets, and custom LoRAs per model.
- **Gear window**: shows which model files are found, which are missing (with download link and size), and lets you
  point a model at a file of your own ("Choose another file…").

## Requirements

| Part | Version |
|---|---|
| Windows | 10 or 11 |
| Graphics card | NVIDIA with **16 GB** VRAM (the only size tested for this release) |
| Python | 3.11 or newer, with "tcl/tk" ticked in the installer ([python.org](https://www.python.org/downloads/windows/)) |
| PhotoCraft | 0.16 or 0.17 (portable). Mask density needs 0.17. |
| ComfyUI | 0.42.0 or newer, running on `http://127.0.0.1:8188` |
| [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) | 2.13.0 or newer (only for Upscale and Refine) |
| Models | the files of the models you want to use, see [Models](#models) |

All other nodes the workflows use are part of ComfyUI itself.

## Install

1. Download this repository: **Code › Download ZIP** and unpack it (e.g. to `C:\programs\photocraft-ai`), or
   `git clone` it.
2. Install **Python** (keep "tcl/tk and IDLE" and "Add python.exe to PATH" ticked).
3. Double-click **`setup-windows.bat`** in the plugin folder. It creates `.venv`, installs Pillow, NumPy,
   websocket-client and tkinterdnd2, and ends with "Setup done".
4. Set up **ComfyUI**, install ComfyUI-AusBoss (ComfyUI-Manager) and put the model files into ComfyUI's model folders.
   ComfyUI reads its model folders only at start, so restart it after adding files.
5. Create the **desktop shortcut**: in the plugin folder, type `powershell` into Explorer's address bar, press Enter,
   then run (with the path to your `photocraft.exe`):

   ```
   .venv\Scripts\python.exe -m pccomfy shortcut --photocraft "C:\programs\photocraft-0.17.0-windows-x64-portable\photocraft.exe"
   ```

   If `setup-windows.bat` said it uses Python directly instead of the virtual environment, use the Python path it
   wrote into `data\python.txt` instead of `.venv\Scripts\python.exe`.
6. **First start**: ComfyUI is running, PhotoCraft is closed. Double-click **PhotoCraft AI** on the desktop.
   PhotoCraft starts, and a few seconds later the plugin window appears. Open the gear window: red entries are model
   files that are still missing.

The shortcut starts PhotoCraft with its control channel (loopback only, token-protected, file access limited to
`data\exchange`) and then the plugin, without a console window. `photocraft-ai.bat` does the same with a console;
set the path to your `photocraft.exe` at the top of it first.

To update: download the new version (or `git pull`) and restart the plugin. Your settings stay in `data\`.

## Models

You only need the files for the models you want to use; the plugin enables what it finds. All direct download links,
sizes, target folders and licences are in [docs/model-downloads.md](docs/model-downloads.md), and the gear window shows
the same links for missing files.

- Release 1 uses the **int8 ConvRot** files, which fit into 16 GB VRAM.
- Some files are **gated**: log in to Hugging Face and accept the licence on the model page first, otherwise the
  download answers "401".
- If you keep models outside ComfyUI, set them up in ComfyUI's `extra_model_paths.yaml`.

## Using it

- **Fill Selection**: describe what should appear in the selection, e.g. "a wooden bench". Hide the layers of earlier
  results before running again.
- **Remove Selection**: select the whole object with a little margin. If the first try didn't work, remove it a second
  time.
- **Expand image**: make the canvas bigger with the Crop tool (Enter) and fill the new area white. An empty prompt often
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

The plugin's code is MIT / Apache-2.0, but **the models have their own licences**, and some of them are
**non-commercial only**: Fibo 2.0 (CC BY-NC 4.0) and the FLUX.2 Klein files. Others ask for credit (the Lenovo
UltraReal LoRA for MOSS: Danrisi). Check [docs/model-downloads.md](docs/model-downloads.md) before you use results
commercially.

## For developers

- **Your own workflows**: build and test a workflow in ComfyUI, export it in API format into `workflows\`, and give the
  nodes the plugin should fill a title: `pc:image`, `pc:mask`, `pc:prompt`, `pc:negative`, `pc:sampler`, `pc:size` /
  `pc:latent`, `pc:output` (more in [pccomfy/workflows.py](pccomfy/workflows.py)). It then shows up as a workflow of
  your own.
- **Command line**: `python -m pccomfy check` (tests both connections), `python -m pccomfy run <mode> -p "…"`
  (one generation), `python -m pccomfy --help` for the rest.
- **Tests**: `python tests/run_all.py` (stubbed Tk, fake PhotoCraft and fake ComfyUI; no GPU needed).
- **Diagnostics**: `data\exchange\last-graph.json` (the last graph sent) and `data\exchange\runs.jsonl` (one line per
  run).
- **PhotoCraft's control channel**: which commands the plugin uses and what would make a native version easier:
  [docs/photocraft-developer-notes.md](docs/photocraft-developer-notes.md).

## Based on

This project started as a fork of [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge)
by Peszemeszek, which drives PhotoCraft from outside over its control channel (`--control`), because PhotoCraft
plug-ins are sandboxed WebAssembly modules without network access. The upstream version targets Linux and SDXL
(with the Fooocus inpaint patch); its README is still available in Polish as [README.pl.md](README.pl.md) and
describes that version, not this one.

## Credits

- [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek, the base of
  this project
- [PhotoCraft](https://github.com/storytold/photocraft) by the ArtCraft team
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and the Comfy-Org model repositories
- [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) (Upscale and Refine)
- The model authors: Black Forest Labs (FLUX.2 / FLUX.3 Klein), Qwen (Qwen-Image 2.1), Bria (Fibo 2.0), Krea (Krea 2),
  MOSS-Image, ByteDance (SeedVR2), obsxrver (FLUX.2 Klein int8 ConvRot), lodestones (MOSS DMD2 LoRA),
  Danrisi (Lenovo UltraReal LoRA), vizsumit (UltraReal LoRA for Flux 2)
- [Lucide](https://lucide.dev) (ISC): the window's icons follow its shapes and style
- [Inter](https://rsms.me/inter/) font by Rasmus Andersson (SIL Open Font License 1.1, see `OFL-Inter.txt`)
- [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) and
  [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion) by Acly, which inspired the upstream inpaint pipeline

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option, like PhotoCraft and the
upstream bridge. The models are not part of this repository and have their own licences (see above).
