# Notes for PhotoCraft developers

These notes come from the upstream README of
[photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) (Peszemeszek) and describe the
upstream version. This fork uses more commands since then; the full check against PhotoCraft 0.15.1 and 0.16 is in
[photocraft-befehle.md](photocraft-befehle.md).

## Why a bridge and not a plug-in

PhotoCraft plug-ins are sandboxed WebAssembly modules (ABI v1). They have no network or file access and only see
the pixels of one layer, so they can't talk to ComfyUI. PhotoCraft does have a **control channel**
(`--control <port>`), a JSON-lines protocol that can run any of its ~900 commands. The bridge drives it from outside.

## Commands used and what would help

The upstream bridge uses only documented control-channel methods: `ui.inspect` (session), `document.inspect`,
`image.duplicate {mergedOnly}`, `app.save` / `app.open`, `layer.new.layer`, `edit.fill`, `select.*` (all, deselect,
rect, reselect), `layer.select`, `layer.flattenImage`, `file.close`, `document.activate`, `edit.copy`,
`edit.paste {center, target:"mask"}`, `edit.pasteSpecial.pasteInto`, `layer.layerMask.revealAll`,
`layer.renameLayer`, `layer.hideLayers` and `image.canvasSize`. It works, but most of that is a workaround for
moving pixels in and out. What would make this (or a proper plug-in) much cleaner:

1. **Pixel I/O over the control channel.** For example `document.renderRegion {rect, scope: composite|layer|selection}`
   that returns a full-resolution base64 PNG (`doc.render` exists, but only headless and capped at 2048 px), plus
   `layer.newFromImage {data, offset, mask?}`. That would remove the temp document, the file round-trips, the tab
   flicker and the *Open Recent* side effects.
2. **Parity between desktop and headless control.** `session.list` and `doc.place` exist in `photocraft-cli serve`
   but not in the desktop channel.
3. **Plug-in ABI v2 with a permissioned network capability** (e.g. localhost only, user-approved) and panels. With that,
   this could be a real Filter › Generative Fill… plug-in with a prompt field.
4. **Native AI (gap G15).** A "bring your own ComfyUI" backend avoids model licensing questions. The plan for a native
   version is a `crates/ai` client (HTTP + WebSocket), `edit.generativeFill` / `edit.generativeExpand` /
   `image.generate` commands run as background jobs with one history step, and a contextual prompt bar under the
   selection.

Also: at `5f65579` (2026-10-16), `crates/engine/src/presets/mod.rs` failed to compile (`Persisted` missing the
`export_presets` field). A one-line fix: `export_presets: take(&mut m, "export_presets"),`.
