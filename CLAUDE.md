# CLAUDE.md: working notes for this repo

Fork of Peszemeszek/photocraft-comfyui-bridge (MIT OR Apache-2.0): a PhotoCraft x ComfyUI plugin for Windows. Local branch `windows-fibo` (main = upstream). The plan and the open work are in `PLAN.md`; read it first. This file is for the working method and is not meant for the public release repo.

## Rules from the user (always)

- If the user writes English: first return the message in corrected English ("**Corrected version of your message:**" + blockquote), then answer. German needs no correction.
- At every decision point, list the options; never pick silently. When unsure (tooltips, wording), ask.
- Side effects (downloads, restarts, deletions, new dependencies) need explicit permission first. The user restarts ComfyUI and the plugin himself.
- The user is not git-experienced: do the git work, explain it in plain words, never ask him to run git.
- Git follows common standards and must stay traceable for the user: one branch per change from `next` (`feat/...`, `fix/...`, `docs/...`), never commit straight onto `next`; tests green, then `git merge --no-ff` into `next`; never push (exception: when the user asks, `git push private next:main` to his private repo philhaderer/photocraft-ai), never rewrite history. After every git step tell him in plain German what happened (branch, commit, where things are now).
- Commit messages: Conventional Commits. Subject `type: short summary` (English, imperative, no full stop, about 70 chars at most), a blank line, then a body that says what and why. Types: `feat` (new function), `fix` (bug fix), `docs` (documentation only), `test` (tests only), `refactor` (code change without new behaviour), `chore` (assets, build and packaging files, housekeeping). One change per commit. Trailer: `Co-Authored-By: Claude <model of the running session> <noreply@anthropic.com>` (e.g. `Claude Opus 5.5`). Commit with `git -c user.name=Claude -c user.email=noreply@anthropic.com commit`. Afterwards remove `.git/*.lock` and `tmp_obj_*` (rename to `.git/stale-*` if deleting is not allowed).
- `README.md` is the GitHub start page (rewritten 29.10. on the user's request): change it only when he asks. `README.pl.md` is upstream and stays untouched.
- `photocraft-ai 0.15.1.bat` was removed on 30.10. by the user's choice. `photocraft-ai.bat` still points to 0.14.0.
- Keep the checkpoint graph and the Fooocus code for now.
- No automatic prompt additions for "remove ...": only the tip under the prompt.
- Only one session does git in this folder (another one switched branches under a running session on 29.10.); other sessions work in their own worktree or read only.
- Tell him before a chat becomes too long and a fresh one is better (see `PLAN.md`, section 6).

## Architecture

- `pccomfy/gui.py`: Tk window: the `App` class with start-up, `_build` (the layout) and the window handling; the rest of `App` lives in mixins: `gui_theme.py` (style, sizes), `gui_prompt.py`, `gui_lora.py`, `gui_modes.py` (tabs, modes, workflow, stages), `gui_state.py` (settings, presets, refresh), `gui_run.py` (generate, undo/redo, progress). `gui_common.py` holds the constants and helpers; `gui.py` re-exports them (`gui.BUILTIN` etc. must keep working). A new method goes into the mixin of its topic. `fonts.py`: loads the shipped Inter font (every font goes through `font()` in gui_common.py). `clipboard.py`: images on the Windows clipboard (read and write). `bridge.py`: runs a request (export layers, build graph, queue, import, undo). `workflows.py`: edits a workflow graph. `models.py`: the models (chips under the function buttons) and their modes, with each mode's workflow and start settings. `comfy.py`: ComfyUI HTTP/WebSocket client. `photocraft.py`: PhotoCraft control port. `winlink.py`: Windows window linking (ctypes). `imaging.py`: masks, boxes, colour match. `config.py`: config and state. `manifest.py`, `inventory.py`, `ui_settings.py`: model detection, preflight and the settings window (gear); `downloads.py` (resumable download with checks), `comfydir.py` (finds ComfyUI's models folder), `ui_downloads.py` (the download symbols, parallel, with the orange site hints). The settings window: "Models" (linked files on top, one tab per model and "Additional") and "Credits". `refslots.py`: the reference slots of Multi Image Edit. `autostart.py` (+ `autostart.pyw`): starts the window with PhotoCraft (environment variables, watcher in the Run key; `python -m pccomfy autostart install|uninstall|status`; not set up, for later). `launcher.py` (+ `photocraft-ai.pyw`): the starter .bat without a console, run by the desktop shortcut (`python -m pccomfy shortcut --photocraft <exe>`). More: `docs/HANDOFF-claude-code.md` (technical notes), `docs/erledigt.md` (what was built when), `docs/archiv/` (old plans and finished research), `docs/prompt-aufbau.md`, `docs/prompting-multi-image.md`.
- `workflows/*.json` are ComfyUI API-format graphs. Nodes the bridge touches carry a title: `pc:image`, `pc:mask`, `pc:prompt`, `pc:sampler`, `pc:size`, `pc:clip`, `pc:output`, `pc:ref`, `pc:latent`, `pc:lora`, `pc:upscale`.
- LoRA names carry the Windows sub-folder (`Moss\lora_dmd2.safetensors`); `fix_lora_names` matches them against ComfyUI's list. ComfyUI reads model folders only at start.
- Diagnostics: `data/exchange/last-graph.json` (last graph sent), `data/exchange/runs.jsonl` (one line per run). `data/` is git-ignored.

## Testing

- `python tests/run_all.py` runs all 68 files (check with `ls tests/test_*.py | wc -l` if it changes) (optional name filter: `python tests/run_all.py bars`); a single file: `python tests/<name>.py` (`test_round5.py` collects the latest rounds). `tests/live_clipboard.py`, `tests/live_dnd.py`, `tests/live_flux2_file_compare.py`, `tests/live_expand_seam.py`, `tests/live_moss_cfg.py`, `tests/live_fill_mask.py`, `tests/live_qwen_encoder.py` and `tests/live_fibo_llm.py` are manual checks (real Windows clipboard, drag and drop, an A/B run of two model files in ComfyUI, the Krea 2 / MOSS Expand seam round with blind rating, MOSS text to image CFG 1.5 against 2.5 with blind pairs, the Fill mask variants on real runs with blind rating, Qwen Edit with its two Qwen3-VL 8B text encoder files blind, Fibo text to image with and without the LLM blind), not part of the runner. They run against a stubbed Tk and a fake PhotoCraft (`FakePC`, new layer IDs on duplicate, unknown IDs rejected like the real one).
- In the cloud VM there is no tkinter and no access to ComfyUI's HTTP API, so the real window and real generations could only be checked by the user. With Claude Code on the user's own machine the real window can be started; real generations still need his permission (GPU). The comfyui tools (queue, history, logs) work.
- New-user test start: `photocraft-ai neuer-nutzer.bat` runs the plugin with its own data folder `data\neuer-nutzer` (`PCCOMFY_HOME`), optionally with `PCCOMFY_SIMULATE_NO_MODELS=1` (ComfyUI's model lists look empty). PhotoCraft must be closed first.
- All tests must pass before a merge. Say plainly what was not tested live.

## What the user calls "perfect" (do not touch without asking)

Qwen 2.1 Edit / Fill / Expand / Remove; Flux 2 and Flux 3 Edit; Flux 3 Upscale; Flux 3 Text to image; MOSS Text to image; Fibo Edit whole image; the window head and sharpness of the window.
Krea 2 and MOSS Expand are switched off since 29.10. (blind test: 2 and 10 of 64 good), parked in `models.PARKED_EXPAND`.

## Release 1 scope

16 GB VRAM (int8 ConvRot files), Windows only. AusBoss stays a declared dependency. 8 GB recommendations are documentation only. A fresh public repo (no upstream history, credits kept) is made shortly before the release.
