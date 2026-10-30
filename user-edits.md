# Editing texts yourself

How to change a visible text without breaking anything, and what to tell Claude afterwards.
Paths are relative to the project folder `C:\programs\photocraft-comfyui-bridge`.

## 1. Find the text

Search the whole folder for the exact words you see in the window, e.g. `Covers these modes`
(VS Code: Ctrl+Shift+F). Usually there is one hit. If there are two, one is a test file (`tests\...`): tell Claude.

## 2. Where which texts live

| What you see | File |
|---|---|
| Settings window (gear): headings, tab titles, info texts, button texts, "Covers these modes:", "Needs these models:" | `pccomfy\ui_settings.py` |
| Download hints in orange, the OK window of a download, status lines of downloads | `pccomfy\ui_downloads.py` |
| Names of the models, tooltips of the function buttons (`FUNCTION_TIPS`), the tips under the prompt (`T2I_TIP`, `EDIT_TIP`, `FILL_TIP`, `MULTI_TIP`, `REMOVE_NAME_TIP` ...) | `pccomfy\models.py` |
| Notes on model files (licence, "gated"), the Credits tab (`CONTRIBUTORS`) | `pccomfy\manifest.py` |
| Names of the functions, the Live preview tip (`LIVE_TIP`), the "LLM" button tip (`LLM_TIP`), other shared texts | `pccomfy\gui_common.py` |
| Main window: labels, buttons and most tooltips | `pccomfy\gui.py` |
| Prompt area (LLM line, "LLM" button, negative prompt), LoRA rows | `pccomfy\gui_prompt.py`, `pccomfy\gui_lora.py` |
| Reference slots of Multi Image Edit | `pccomfy\refslots.py` |
| History list (clock in the header): "Erase history", "No runs yet." | `pccomfy\gui_run.py` |
| Right-click menu on a model (Save current settings, Load default settings, Favourite, Hide) | `pccomfy\gui_modes.py` |
| GitHub start page | `README.md` (change it only when you ask Claude) |

Not here: `README.pl.md` is upstream and stays as it is.

## 3. What you may change, and what not

- Change only the words **between the quotation marks**.
- Keep everything in `{curly braces}` (e.g. `{name}`), `\n` (new line) and `\u2713` style codes as they are.
- A long text can be split into several quoted pieces over several lines; they belong together.
- Do not edit names that are used as keys, such as `"txt2img"` or `"flux3"`; they are not visible texts.

## 4. After editing: tell Claude

Save the file, then write something like:

> I edited `pccomfy\ui_settings.py`: "Covers these modes:" is now "Works with these modes:".

Claude then checks your change (`git diff`), runs all tests, makes a branch and a commit with a proper message,
merges it into `next`, and explains in plain German what happened. Tests that check the old wording are adjusted.

Please:

- **Do not commit yourself** (not in VS Code either). Claude does the Git part, so the history stays clean.
- **Do not edit while Claude is working** on something else in the same folder; your change would end up in its commit.
  Wait until Claude says it is done.
- Several texts at once are fine: list the files in one message.

## 5. If the window does not start after your edit

A quote or a bracket is probably missing. Tell Claude the file name; it fixes it. Your last good state is always
in Git, nothing is lost.

---
*Claude keeps this file up to date: when a text moves to another file, a new file gets visible texts, or the workflow changes (rule in `CLAUDE.md`).*
