# Draft: tips of the day (tooltips)

Draft for PLAN point 16 ("daily tooltips"). 30 tips, each checked against the code (paths relative to `pccomfy/`). Shortened by the user on 31.10.
About one third points to core functions, two thirds to things that are easy to miss. The wording is a proposal; the user decides.

## Prompting

1. Fill Selection: select an area and describe only what should appear there, e.g. "a red flower". Hide old result layers before the next run.
   Source: `models.FILL_TIP`, `models.FUNCTION_TIPS["inpaint"]`

2. Remove Selection: keep the whole object inside the selection. Text is optional; you can name it ("the dog").
   Source: `models.FUNCTION_TIPS["remove"]`, `models.REMOVE_NAME_TIP`, `Mode.remove_text`

3. Fibo 2.0 Edit Turbo or Flux 2: if Remove Selection leaves a trace, run it a second time.
   Source: `models.REMOVE_AGAIN`, used in the `remove` mode of FLUX2 and FIBO in `models.py`

4. To remove something with Edit Canvas, say what replaces it: "Remove the dog and paint the wall behind him".
   Source: `models.EDIT_TIP`

5. Expand image: crop outward with the Crop tool (Enter), fill the new area white, and try an empty prompt first. Expand big areas in small steps.
   Source: `models.FUNCTION_TIPS["outpaint"]`, `gui_common.EXPAND_HINT`

6. In Multi Image Edit your PhotoCraft picture is image 1 and slot 1 is image 2. Click the tag under a slot to add it to your prompt.
   Source: `refslots.py` (`lbl_refnames` text, `_refs_insert_tag` bound to the tag label)

7. Drag a slot picture into the prompt box: its tag lands where you let go, and the text cursor shows the spot.
   Source: `refslots._refs_drag_move`, `_refs_drag_drop`

8. "Describe" on a slot writes "<name>: description" as its own line into your prompt. Edit or delete it freely.
   Source: `refslots._refs_describe` (docstring), `docs/prompt-aufbau.md` point 3

9. Flux 3 Multi Image Edit with BBOX: draw a rectangle selection, put a reference in slot 1 and name the object in the prompt, e.g. "car".
   Source: `refslots.BBOX_TIP`, `refslots.BBOX_CHECK_TIP`, `Model.bbox` (Flux 3 only)

10. With BBOX and no <obj_1> in your text, the plugin adds "Place the result in <obj_1>." Your selection stays after the run.
    Source: `bridge.BBOX_SENTENCE` (used around line 666 of `bridge.py`), PLAN.md point 15

## Selections and masks

11. Edge feather softens the seam, in % of the selection's shorter side. It shows up with the soft layer mask (Fill, Remove); 0 = hard edge.
    Source: `gui.py` tooltip of `w_feather`, `gui_modes._update_feather_state`; it sits in "Advanced settings" (`f_post` in `adv_body`)

12. Mask density: 100 % shows only the selection with its soft edge, 0 % the whole redrawn area. You can change it later in PhotoCraft.
    Source: `gui.py` tooltip of `w_density` ("... in PhotoCraft's layer mask properties")

13. "Show feather" paints the blend area red in PhotoCraft (Quick Mask). Click it again, or Generate, to get your selection back.
    Source: `gui.py` tooltip of `b_fprev`, `gui_run.toggle_feather_preview`

14. Match colours (Fill Selection only) pulls the new area's saturation back toward its surroundings. 0 = off.
    Source: `gui.py` tooltip of `w_match`; `gui_modes._on_mode_ui` shows `_match_widgets` only for `inpaint`

15. Qwen fills small selections badly. Use a larger selection, or try Fibo 2.0 Edit Turbo.
    Source: `models.QWEN_SMALL`, `models.RANKING["inpaint"]` (Fibo first)

16. With Qwen, "Seam correction (A/B)" evens out a rim at the border. Each result comes twice: "[seam fix]" on top, "[raw]" hidden below.
    Source: `gui.py` tooltip of `cb_seam`; shown only for `Model.seam == "switch"` (Qwen), `gui_modes._update_availability`

## Models and files

17. Right-click a model chip: "Set as my settings" keeps the current sliders, sampler, steps and LoRAs for this function and model; "Reset page" brings them back.
    Source: `gui_modes._chip_menu`, `_save_page`, `gui.py` (`b_reset`), `gui_common.PAGE_NOT_SAVED`

18. A Favourite is the model a function opens with when you switch to it. Hidden models come back with a tick in the gear window.
    Source: `gui_modes._model_for_mode`; `ui_settings.py` tooltip "Untick to hide this model in the plugin, tick to show it again."

19. Hover a function button: the tooltip starts with the model ranking for it, e.g. Fill Selection: 1. Fibo, 2. Qwen.
    Source: `models.ranking_text`, `models.function_tip`, `models.RANKING`

20. MOSS does text to image only. Turn Steps up to 35 for best results; Krea 2 is the fast text to image model.
    Source: `models.MOSS_STEPS_TIP`, `MOSS.tip`, `KREA2.tip`

21. The gear window lists the files each model needs. The chain icon links a file ComfyUI already has under another name.
    Source: `ui_settings.py` (chain icon, `_link_hints`), PLAN.md 14c step 3

22. The disk icon in the gear window downloads a file; right-click it to copy the download link.
    Source: `ui_settings._link_menu` (menu item "Copy download link"), `ui_settings.py` line ~728

## Speed and VRAM

23. Click the small "x1" piece on the right of Generate to make 1 to 8 variants in one run. They land together in one group in PhotoCraft.
    Source: `gui.py` (`w_variants`, `m_variants`, range 1 to 8), `gui_run.py` (`req.group_name`)

24. "Live preview" shows the picture while it is made. It is greyed out until the model's preview decoder file is downloaded.
    Source: `gui_common.LIVE_TIP`; PLAN.md section 1 (Live preview greyed out while the decoder is missing)

25. MOSS text to image is best without the DMD2 speed LoRA: 35 steps at CFG 3.0. The LoRA (8 steps) is faster but looks more artificial.
    Source: comment above `MOSS` in `models.py` (blind test 29.10.), `MOSS_STEPS_TIP`

## Window and shortcuts

26. Ctrl+Enter generates. Esc or Ctrl+Alt+Enter cancels the run.
    Source: `gui.py` (`<Control-Return>`, `<Control-Alt-Return>`, `<Escape>`, tooltips of `b_go` and `b_stop`)

27. The clock in the header lists your last 20 runs. Click one to load its settings with a new seed; nothing starts by itself.
    Source: `history.KEEP`, `gui.py` tooltip of `b_history`, `gui_run.load_history`

28. Click a value box next to a slider and type a number. Double-click selects just the number; Up and Down step the value.
    Source: `gui_common.ValueBox` (docstring, `<Double-Button-1>`, `<Up>`, `<Down>`)

29. The LLM button describes the picture in PhotoCraft and adds the text to the end of your prompt on a new line. Ctrl+Z in the field undoes it.
    Source: `gui_common.LLM_TIP`, `gui_prompt.describe_canvas` (docstring: "in one undo step")
30. Upscale and Refine: the "Mix source/new image" slider blends the plain scaled original into the result; below 100 % it tames over-sharp results.
    Source: `gui.py` tooltip of `w_detail` ("100 % = only the new image; less mixes in the plain scaled original"), `bridge.run` (`req.detail`)

## Left out on purpose (user, 31.10.)

The LLM time ("about 20 s"), the status line's slow steps, minimise / double-click on the header, Fibo with a rectangle selection, Flux 3 Upscale without SeedVR2, the trash icon, VRAM numbers, Fooocus.

## Not verified

- Turbo/speed LoRA switch: the code only calls it "the workflow's own LoRA", so no speed claim is made.
