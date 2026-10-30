# Function symbols

Optional: one PNG per function button, named after the function's key. Without a file the button shows its built-in
symbol (`fn-<key>` in pccomfy/icons.py; Image → image, only for a workflow of your own, shows a rounded square).

| File | Button |
|---|---|
| `txt2img.png` | Text to image |
| `outpaint.png` | Expand image |
| `inpaint.png` | Fill Selection |
| `remove.png` | Remove Selection |
| `edit.png` | Edit Canvas |
| `multi_edit.png` | Multi Image Edit |
| `upscale.png` | Upscale (new file) |
| `refine.png` | Refine (same size) |
| `img2img.png` | Image → image (only for a workflow of your own) |

The plugin takes only the shape: the transparent parts stay empty, everything else is filled with the button's colour
(light on a dark button, dark on the orange, chosen one, grey when greyed out). Without transparency, the dark pixels
are the shape. Any size works; it is scaled to 20 px (times the display scaling). Square, simple line symbols at
about 96 px or more look best. Restart the plugin after adding a file.
