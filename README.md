<div align="center">

# PhotoCraft AI

**Text to Image, Fill, Remove, Expand, Edit, Upscale and more — inside PhotoCraft, running locally in ComfyUI.**

Tested: Windows 11 · 16 GB VRAM · PhotoCraft 0.18 · ComfyUI version: 0.42.0 

<sub>Replace Photoshop's generative AI features with locally running models. Supports: MOSS Image, Krea 2 Turbo, Flux 3 Image Klein, Flux 2 Image Klein, Qwen 2.1 Edit and Fibo 2.0 Edit Turbo  </sub>

</div>

---

> Unofficial community project, not affiliated with PhotoCraft, ArtCraft or Storyteller. PhotoCraft is in early alpha
> and so is this plugin. "PhotoCraft AI" is a working title.

## Quick start

1. **Get the parts**: Windows 10/11 with an NVIDIA card (16 GB VRAM), [Python 3.11+](https://www.python.org/downloads/windows/)
   (tick "tcl/tk" and "Add python.exe to PATH"), PhotoCraft 0.18, and ComfyUI 0.42 or newer with
   [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) 2.13 or newer (only needed for modes Upscale and Refine ).
2. **Install the plugin**: *Code › Download ZIP*, unpack it, double-click **`setup-windows.bat`**. It also creates the
   desktop shortcut **PhotoCraft AI** (it looks for `photocraft.exe` itself and asks once if it can't find it).
3. **Start it**: start ComfyUI, close PhotoCraft, then double-click **PhotoCraft AI** on your desktop. PhotoCraft opens,
   and a few seconds later the plugin window appears.
4. **Get the models**: open the plugin's settings window (gear symbol). Under **Easy Mode** one button downloads the two starter models
   (Flux 3 Klein Image and Fibo 2.0 Edit Turbo, about 20 GB), which cover all six Easy Mode functions. Flux 3 needs a free Hugging Face login
   once (the button opens its page). Restart ComfyUI afterwards.
5. In the plugin window switch on **Easy Mode**, pick a function, type a prompt, press **Generate** (Ctrl+Enter).

Easy Mode shows only the basic function buttons and the prompt; the plugin picks the best installed model and its tested
settings. Refine and Multi Image Edit are not part of Easy Mode: switch it off to use them and to get all settings. 

Download all models via the settings tabs to get the full experience!

## What it does

You pick a **function** at the top, type a prompt and press **Generate**. The plugin sends the picture (or the selection) 
to ComfyUI and puts the result back into PhotoCraft as a new layer in a group, with a soft layer mask where that makes sense.

More settings in the window: **variants** (generates several results as layers in one group), prompt history, prompt templates,
LLM prompt enhancement, live preview. Advanced settings: **edge feather, context size, mask density (PhotoCraft 0.17+), 
**add custom LoRAs, sharpen, match colours.**


| Function | What it does |
|---|---|
| **Text to image** | A new picture from text only, as a new layer. |
| **Expand image** | Extend the canvas with the Crop tool, fill the new area white; the plugin paints it. |
| **Fill Selection** | Select an area, type what should appear there. |
| **Remove Selection** | Select an object, with a little margin around it; it is removed and the background filled in. |
| **Edit Canvas** | Changes the whole picture from your text ("make it night"). |
| **Multi Image Edit** | Edits the picture with reference images (drop or paste images into the slots). |
| **Upscale (new file)** | Enlarges the picture or selection into a new document, up to 24 MP. |
| **Refine (same size)** | Cleans up the picture or selection at the same size, as a new layer. |


Which model offers which function:

| | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Fill Selection | | | ✓ | ✓ | | |
| Remove Selection | ✓ | ✓ | ✓ | ✓ | | |
| Expand image | ✓ | ✓ | ✓ | ✓ | | |
| Edit Canvas | ✓ | ✓ | ✓ | ✓ | | |
| Multi Image Edit | ✓ | ✓ | ✓ | ✓ | | |
| Upscale (new file) | ✓ | ✓ | | | | |
| Refine (same size) | | ✓ | | ✓ | | |
| Text to image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |


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

You only need the files for the models you want. The gear window lists the files each model needs, with size, ComfyUI target
folder and a download button; the plugin enables a model when it finds all the files for its standard settings.

- Release 1 uses the **int8 ConvRot** files, which fit into 16 GB VRAM, some even into 12 GB.
- Some files are **gated**: log in to Hugging Face and accept the licence on the model page first. Flux 3 is one of them.


## Known limitations

- Only tested on Windows with a 16 GB NVIDIA card.
- During a run, PhotoCraft briefly opens a temporary document. PLease don't switch documents or change the
  selection while a run is going.
- A run consists of several PhotoCraft steps (history entries).
- CMYK, Lab and 16-bit documents go through 8-bit RGB.

## Licences of the models

The plugin's code is MIT / Apache-2.0, but **the models have their own licences**, and several limit commercial use.
This is a summary of what the model pages state, not legal advice; read the licence on each model page before you use
results commercially.

| Model | Licence | Commercial use |
|---|---|---|
| Flux 3 (Klein) and its LoRAs | FLUX Kommunity License | Free only below a yearly revenue limit (USD 5 million, with conditions); above that you need a licence from Black Forest Labs |
| Flux 2 (Klein) | FLUX non-commercial | No |
| Qwen (Qwen-Image 2.1) | Qwen Research License | No (research and evaluation only); products must say "Built with Qwen" |
| Fibo 2.0 | CC BY-NC 4.0 | No |
| Krea 2 | Krea 2 Community License | See the licence on its model page |
| MOSS | Apache 2.0 | Yes |

Other files: the Lenovo UltraReal LoRA for MOSS asks for credit (Danrisi), the Qwen3-VL and Qwen 3.5 text encoders,
SeedVR2 and the MOSS LoRAs are Apache 2.0, BiRefNet is MIT.

## Credits

- [PhotoCraft](https://github.com/storytold/photocraft) by the ArtCraft team
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and the Comfy-Org model repositories
- [ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) (Upscale and Refine)
- [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek, the starting
  point of this project (MIT / Apache-2.0)
- The model authors: Black Forest Labs (Flux 2 / Flux 3 Klein), Qwen (Qwen-Image 2.1), Bria (Fibo 2.0), Krea (Krea 2),
  MOSS-Image, ByteDance (SeedVR2), obsxrver (Flux 2 Klein int8 ConvRot), lodestones (MOSS DMD2 LoRA), Danrisi (Lenovo
  UltraReal LoRA), vizsumit (UltraReal LoRA for Flux 2)
- [Lucide](https://lucide.dev) (ISC): the window's icons follow its shapes and style
- [Inter](https://rsms.me/inter/) font by Rasmus Andersson (SIL Open Font License 1.1, see
  [pccomfy/assets/fonts/OFL-Inter.txt](pccomfy/assets/fonts/OFL-Inter.txt))

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option. The models are not part of this
repository and have their own licences (see above).
