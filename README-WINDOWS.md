# PhotoCraft x ComfyUI bridge: Windows + Fibo Edit

Local changes on top of the upstream bridge (Peszemeszek/photocraft-comfyui-bridge):

- Windows: config, token and exchange files live in `data\`, workflows in `workflows\`.
- `setup-windows.bat` (once), `photocraft-ai.bat` (every time), `check-windows.bat` (diagnostics).
- Workflow titles can carry several tags (`pc:prompt pc:size`), and `pc:prompt` also fills a `prompt` field.
- `*.group.json` runs several workflows per edit with the same crop, mask and seed.
- Fibo Edit Turbo workflows: `fibo2-edit-plain.json`, `fibo2-edit-vgl.json`, `fibo2-edit-both.group.json`.

## Use

1. Run `setup-windows.bat` once.
2. Close PhotoCraft, then start `photocraft-ai.bat`. It starts PhotoCraft with `--control` and opens the bridge window.
3. Open an image in PhotoCraft, make a selection, pick mode "Generative fill", type the edit as an instruction
   ("Make the jacket red") and press Generate (Ctrl+Enter).
4. The result is a new layer with a soft layer mask. With the "both" workflow you get two layers, `[plain]` on top and
   `[vgl]` hidden below it. Toggle the eye icons to compare.

Fibo is an instruction editor, so write what to change, not what the selection should contain.
It sees the selection plus some surrounding context (the "Context" setting) and the layer mask limits the change to the selection.

Modes that fit the Fibo workflows: Generative fill and Image to image. Text to image and Expand have no source image for Fibo.

## Presets (save and load)

The **Preset** row at the top of the window saves and loads everything in the window, including the prompt:
mode, workflow, text model, denoise, base res., context, mask grow/blur, variants, layer mask and so on.

- Pick a preset in the dropdown to load it.
- **Save** overwrites the selected preset, **Save as...** creates a new one, **Delete** removes it.
- Presets are plain JSON files in `presets\`. Git tracks them, so you can share or revert them.
- If a preset refers to a workflow or text model this machine does not have, the rest is still applied and the
  status line lists what was skipped.

## Git

Work happens on the `windows-fibo` branch. `main` is the untouched upstream version.
`git log --oneline` shows the steps, `git revert <commit>` or `git checkout <commit> -- <file>` undoes one.

## VGL writer

`fibo2-edit-vgl.json` uses `qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors` as the local LLM (the one in your
`fibo_2_edit_turbo_image_edit_vgl_existingQwen` workflow). Pick another text model in the bridge window ("Text model"). It fills every CLIPLoader node titled `pc:clip`.

## Tests

`python tests/test_group_workflows.py` (fake PhotoCraft and fake ComfyUI, no GPU, no PhotoCraft needed)
`python tests/test_gui_presets.py` (preset logic with a stubbed Tk, no window needed)
