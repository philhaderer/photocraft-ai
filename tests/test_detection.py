"""Model detection: manifest, inventory, resolve, tab and mode status, preflight, apply_names, comfy.inventory_raw, settings.

    python tests/test_detection.py
"""
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp()
try:
    import tomllib  # noqa: F401
except ImportError:  # the checks below do not read toml
    sys.modules["tomllib"] = types.SimpleNamespace(load=lambda f: {})
sys.path.insert(0, str(ROOT))

from pccomfy import comfy, config as cfgmod, inventory, manifest, models  # noqa: E402

LOADERS = {cls: (kind, fld) for kind, (cls, fld, _f) in manifest.KINDS.items()}


def workflow_files(name):
    """{(kind, file name)} a shipped workflow loads."""
    g = json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))
    out = set()
    for n in g.values():
        if isinstance(n, dict) and n.get("class_type") in LOADERS:
            kind, fld = LOADERS[n["class_type"]]
            v = (n.get("inputs") or {}).get(fld)
            if isinstance(v, str):
                out.add((kind, v))
    return out


def full_lists():
    lists = {k: [] for k in manifest.KINDS}
    for f in manifest.FILES.values():
        lists[f.kind].append(f.name)
    return lists


def test_manifest():
    for f in manifest.FILES.values():
        assert f.kind in manifest.KINDS, f
    assert manifest.FILES["Moss\\lora_dmd2.safetensors"].target == "models\\loras\\Moss"
    assert manifest.FILES["flux2-vae.safetensors"].target == "models\\vae"
    for key, tab in manifest.TABS.items():
        assert key in models.BY_KEY, key
        for n in tab.required + tab.optional:
            assert n in manifest.FILES, (key, n)
        for mode, spec in tab.modes.items():
            assert mode in models.BY_KEY[key].modes, (key, mode)
            for n in spec.requires + spec.optional:
                assert n in manifest.FILES, (key, mode, n)
    # models.requires carries the tab's required files, in sync with the manifest
    for m in models.MODELS:
        assert m.key in manifest.TABS, m.key
        assert tuple(m.requires) == manifest.tab_required(m.key), m.key
        assert m.requires, m.key


def test_workflows_covered():
    """Every model file a shipped workflow loads is known to the manifest for that tab and mode (required or optional)."""
    for m in models.MODELS:
        for mode, mo in m.modes.items():
            known = set(manifest.mode_required(m.key, mode)) | set(manifest.mode_optional(m.key, mode))
            for kind, name in workflow_files(mo.workflow):
                assert name in manifest.FILES, (m.key, mode, name, "not in the manifest")
                assert manifest.FILES[name].kind == kind, (name, kind)
                assert name in known, (m.key, mode, name, "loaded by the workflow but not listed for this tab/mode")
            # and nothing the manifest calls required is unknown to the workflow
            loaded = {n for _k, n in workflow_files(mo.workflow)}
            for name in manifest.mode_required(m.key, mode):
                assert name in loaded, (m.key, mode, name, "required but the workflow does not load it")


def test_resolve():
    av = ["Moss\\lora_dmd2.safetensors", "flux2-vae.safetensors", "Sub/Folder/qwen_3_8b_fp8mixed.safetensors"]
    assert inventory.resolve("flux2-vae.safetensors", av) == "flux2-vae.safetensors"
    assert inventory.resolve("moss/LORA_DMD2.safetensors", av) == "Moss\\lora_dmd2.safetensors"          # separator and case
    assert inventory.resolve("qwen_3_8b_fp8mixed.safetensors", av) == "Sub/Folder/qwen_3_8b_fp8mixed.safetensors"   # sub-folder
    assert inventory.resolve("nothing.safetensors", av) is None
    assert inventory.resolve("a.safetensors", ["x/a.safetensors", "y/a.safetensors"]) is None            # two candidates: no guess
    assert inventory.resolve("seedvr2_ema_vae_fp16.safetensors", ["ema_vae_fp16.safetensors"],
                             aliases=("ema_vae_fp16.safetensors",)) == "ema_vae_fp16.safetensors"        # alias
    assert inventory.resolve("flux2-vae.safetensors", ["my_vae.safetensors"], {"flux2-vae.safetensors": "my_vae.safetensors"}) == "my_vae.safetensors"
    assert inventory.resolve("flux2-vae.safetensors", ["flux2-vae.safetensors"], {"flux2-vae.safetensors": "gone.safetensors"}) == "flux2-vae.safetensors"


def test_status():
    inv = inventory.Inventory(full_lists(), nodes=set(n for t in manifest.TABS.values() for s in t.modes.values() for n in s.nodes))
    for m in models.MODELS:
        assert inv.tab_status(m.key).state == "ready", m.key

    # a missing optional extra (Moss speed LoRA) is only a note
    lists = full_lists()
    lists["lora"].remove("Moss\\lora_dmd2.safetensors")
    st = inventory.Inventory(lists, nodes=inv.nodes).tab_status("moss")
    assert st.state == "ready" and [f.name for f in st.optional_missing] == ["Moss\\lora_dmd2.safetensors"]

    # SeedVR2 missing: Flux 3 stays usable, only Upscale is greyed
    lists = full_lists()
    lists["unet"].remove("seedvr2_3b_int8_convrot.safetensors")
    i2 = inventory.Inventory(lists, nodes=inv.nodes)
    st = i2.tab_status("flux3")
    assert st.state == "partial" and list(st.detail) == ["upscale"], st
    assert i2.mode_status("flux3", "edit").state == "ready" and i2.mode_status("flux3", "upscale").state == "missing"
    assert [f.name for f in i2.mode_status("flux3", "upscale").missing] == ["seedvr2_3b_int8_convrot.safetensors"]

    # the Flux 3 diffusion model missing: the whole tab is out
    lists = full_lists()
    lists["unet"].remove("flux3-image-klein-int8-convrot.safetensors")
    st = inventory.Inventory(lists, nodes=inv.nodes).tab_status("flux3")
    assert st.state == "missing" and [f.name for f in st.missing] == ["flux3-image-klein-int8-convrot.safetensors"]

    # Qwen: the text-to-image text encoder is another file than the edit one
    lists = full_lists()
    lists["clip"].remove("qwen3vl_8b_int8_convrot.safetensors")
    i3 = inventory.Inventory(lists, nodes=inv.nodes)
    st = i3.tab_status("qwen")
    assert st.state == "partial" and list(st.detail) == ["txt2img"]

    # every mode missing its own file = the tab is missing (Flux 2 with no Ultra-real LoRA is only partial)
    lists = full_lists()
    lists["lora"].remove("Flux 2\\ultra_real_v4.safetensors")
    assert inventory.Inventory(lists, nodes=inv.nodes).tab_status("flux2").state == "partial"

    # a missing AusBoss node blocks Flux 3 Upscale, and the message names the pack
    i4 = inventory.Inventory(full_lists(), nodes={"SeedVR2Preprocess"})
    ms = i4.mode_status("flux3", "upscale")
    assert ms.state == "missing" and "AUSBOSS_NODES_TiledUpscale" in ms.nodes
    assert any("ComfyUI-AusBoss" in ln for ln in inventory.preflight(i4, "flux3", "upscale"))
    # node classes not read (None): never a reason to block
    assert inventory.Inventory(full_lists(), nodes=None).mode_status("flux3", "upscale").state == "ready"

    # nothing installed: everything is missing, nothing raises
    empty = inventory.Inventory({})
    assert all(empty.tab_status(m.key).state == "missing" for m in models.MODELS)


def test_rows_and_texts():
    lists = full_lists()
    lists["vae"].remove("qwen_image_vae.safetensors")
    inv = inventory.Inventory(lists)
    rows = {r["key"]: r for r in inv.rows()}
    assert [r["key"] for r in inv.rows()] == [m.key for m in models.MODELS]
    assert rows["krea2"]["status"].state == "missing"
    krea = {f.name: (found, level) for f, found, level in rows["krea2"]["files"]}
    assert krea["qwen_image_vae.safetensors"] == (None, "required")
    assert krea["krea2_turbo_int8_convrot.safetensors"][0] == "krea2_turbo_int8_convrot.safetensors"
    assert any(level == "optional" for _f, _fd, level in rows["moss"]["files"])

    lines = inventory.preflight(inv, "krea2", "txt2img")
    assert lines == ["missing: qwen_image_vae.safetensors -> ComfyUI\\models\\vae"], lines
    msg = inventory.short_message(lines, "Krea 2 Turbo")
    assert msg.startswith("Krea 2 Turbo: missing: qwen_image_vae.safetensors -> ComfyUI\\models\\vae") and "Restart ComfyUI" in msg
    lines2 = inventory.preflight(inventory.Inventory({}), "flux3", "edit")
    assert len(lines2) == 3 and "(download: https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy)" in lines2[0]
    assert "(+2 more, see Settings)" in inventory.short_message(lines2)
    assert inventory.preflight(None, "flux3", "edit") == [] and inventory.preflight(inv, "", "edit") == []
    assert inventory.preflight(inv, "unknown", "edit") == []         # a workflow of your own is never blocked
    assert inventory.short_message([]) == ""
    t = inventory.tooltip_text(inv.tab_status("krea2"))
    assert t == "Missing: qwen_image_vae.safetensors. Set in settings (gear)." and inventory.tooltip_text(inventory.Status("ready")) == ""


def test_graph_names():
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux3-image-klein-int8-convrot.safetensors"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "FLUX2-VAE.safetensors"}},
        "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "Moss\\lora_dmd2.safetensors", "model": ["1", 0]}},
        "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": "gone.safetensors"}},
        "5": {"class_type": "SomeCustomNode", "inputs": {}},
    }
    lists = {"unet": ["flux3-image-klein-int8-convrot.safetensors"], "vae": ["flux2-vae.safetensors"],
             "lora": ["Moss/lora_dmd2.safetensors"], "clip": []}
    inv = inventory.Inventory(lists, nodes={"UNETLoader", "VAELoader", "LoraLoaderModelOnly", "CLIPLoader"})
    files, classes = inv.check_workflow(g)
    assert files == [("clip", "gone.safetensors")] and classes == ["SomeCustomNode"], (files, classes)
    assert inv.apply_names(g) == 2
    assert g["2"]["inputs"]["vae_name"] == "flux2-vae.safetensors" and g["3"]["inputs"]["lora_name"] == "Moss/lora_dmd2.safetensors"
    assert g["1"]["inputs"]["unet_name"] == "flux3-image-klein-int8-convrot.safetensors"
    assert g["4"]["inputs"]["clip_name"] == "gone.safetensors"          # nothing to rename it to
    assert inv.apply_names(g) == 0
    # the shipped workflows pass against a full install
    full = inventory.Inventory(full_lists())
    for m in models.MODELS:
        for w in m.workflows():
            graph = json.loads((ROOT / "workflows" / w).read_text(encoding="utf-8"))
            files, _ = full.check_workflow(graph)
            assert not files, (w, files)


class FakeComfy(comfy.ComfyUI):
    """A ComfyUI that answers from a dict instead of HTTP."""

    def __init__(self, lists, up=True, all_nodes=True):
        super().__init__()
        self.lists, self.up, self.all_nodes = lists, up, all_nodes

    def _json(self, path, payload=None):
        if not self.up:
            raise comfy.ComfyError("No connection to ComfyUI")
        if path == "/system_stats":
            return {"system": {}}
        if path == "/object_info":
            if not self.all_nodes:
                raise comfy.ComfyError("boom")
            return {"UNETLoader": {}, "AUSBOSS_NODES_Seed": {}}
        node = path.rsplit("/", 1)[1]
        field = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name", "LoraLoaderModelOnly": "lora_name"}[node]
        kind = {v[0]: k for k, v in manifest.KINDS.items()}[node]
        return {node: {"input": {"required": {field: [self.lists[kind], {}]}}}}


def test_comfy_reading():
    lists = full_lists()
    c = FakeComfy(lists)
    raw = c.inventory_raw()
    assert raw["unet"] == lists["unet"] and raw["lora"] == lists["lora"] and raw["nodes"] == {"UNETLoader", "AUSBOSS_NODES_Seed"}
    inv = inventory.fetch(c, {"x": "y"})
    assert inv.tab_status("flux3").state == "partial" or inv.tab_status("flux3").state == "ready"
    assert inv.mapping == {"x": "y"}
    assert FakeComfy(lists, all_nodes=False).inventory_raw()["nodes"] is None          # node list unreadable: not fatal
    try:
        FakeComfy(lists, up=False).inventory_raw()
        raise AssertionError("an unreachable server must raise, not look like an empty install")
    except comfy.ComfyError:
        pass
    # the new-style combo spec ["COMBO", {"options": [...]}] reads too
    c2 = FakeComfy(lists)
    c2._json = lambda path, payload=None: ({"system": {}} if path == "/system_stats" else {path.rsplit("/", 1)[1]: {"input": {"required": {
        "unet_name": ["COMBO", {"options": ["a.safetensors"]}], "clip_name": ["COMBO", {"options": ["b"]}],
        "vae_name": ["COMBO", {"options": ["c"]}], "lora_name": ["COMBO", {"options": ["d"]}]}}}})
    assert c2.inventory_raw()["unet"] == ["a.safetensors"]


def test_settings():
    assert cfgmod.model_map() == {} and cfgmod.favorites() == {} and cfgmod.hidden_tabs() == set() and cfgmod.extra_paths_file() == ""
    cfgmod.set_model_link("flux2-vae.safetensors", "my_vae.safetensors")
    cfgmod.set_model_link("a.safetensors", "b.safetensors")
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors", "a.safetensors": "b.safetensors"}
    cfgmod.set_model_link("a.safetensors", "")
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"}
    cfgmod.set_extra_paths_file("C:\\x\\extra_model_paths.yaml")
    assert cfgmod.extra_paths_file() == "C:\\x\\extra_model_paths.yaml"
    cfgmod.set_favorite("inpaint", "qwen")
    cfgmod.set_favorite("remove", "fibo")
    cfgmod.set_favorite("remove", None)
    assert cfgmod.favorites() == {"inpaint": "qwen"}
    cfgmod.set_tab_hidden("krea2", True)
    cfgmod.set_tab_hidden("moss", True)
    cfgmod.set_tab_hidden("moss", False)
    assert cfgmod.hidden_tabs() == {"krea2"}
    saved = json.loads(cfgmod.SETTINGS_FILE.read_text(encoding="utf-8"))
    assert set(saved) == {"model_map", "extra_paths_file", "favorites", "hidden_tabs"}
    cfgmod.SETTINGS_FILE.write_text("not json", encoding="utf-8")       # a broken file is an empty settings file
    assert cfgmod.model_map() == {} and cfgmod.hidden_tabs() == set()
    # the window state file is separate and untouched
    assert cfgmod.STATE_FILE != cfgmod.SETTINGS_FILE


def test_extra_paths():
    text = (
        "# comment\r\n"
        "comfyui:\r\n"
        "    base_path: C:/AI_Models/\r\n"
        "    is_default: true\r\n"
        "    checkpoints: models/checkpoints/\r\n"
        "    diffusion_models: |\r\n"
        "        models/diffusion_models\r\n"
        "        D:/Other/unet   # second place\r\n"
        "    vae: \"models/vae\"\r\n"
        "    loras:\r\n"
        "        - models/loras\r\n"
        "        - \"E:/Loras\"\r\n"
        "\n"
        "a111:\n"
        "    base_path: /opt/a1111\n"
        "    text_encoders: models/te\n"
    )
    secs = inventory.parse_extra_paths(text)
    assert [s["name"] for s in secs] == ["comfyui", "a111"]
    c = secs[0]
    assert c["base_path"] == "C:/AI_Models/"
    assert c["folders"]["diffusion_models"] == ["C:/AI_Models/models/diffusion_models", "D:/Other/unet"]
    assert c["folders"]["vae"] == ["C:/AI_Models/models/vae"] and c["folders"]["checkpoints"] == ["C:/AI_Models/models/checkpoints/"]
    assert c["folders"]["loras"] == ["C:/AI_Models/models/loras", "E:/Loras"], c["folders"]["loras"]
    assert "is_default" not in c["folders"]
    assert secs[1]["folders"] == {"text_encoders": ["/opt/a1111/models/te"]}
    assert inventory.parse_extra_paths("") == [] and inventory.parse_extra_paths("garbage without colon\n  - x\n") == []
    assert inventory.parse_extra_paths("only:\n")[0]["folders"] == {}
    assert inventory.read_extra_paths(Path(os.environ["PCCOMFY_HOME"]) / "does-not-exist.yaml") == []


def test_find_on_disk():
    base = Path(tempfile.mkdtemp())
    (base / "models" / "diffusion_models").mkdir(parents=True)
    (base / "models" / "vae" / "sub").mkdir(parents=True)
    (base / "models" / "diffusion_models" / "seedvr2_3b_int8_convrot.safetensors").write_bytes(b"")
    (base / "models" / "vae" / "sub" / "ema_vae_fp16.safetensors").write_bytes(b"")        # the alias of the SeedVR2 VAE, in a sub-folder
    (base / "models" / "vae" / "other.safetensors").write_bytes(b"")
    yaml = f"x:\n    base_path: {base.as_posix()}\n    diffusion_models: models/diffusion_models\n    vae: models/vae\n    loras: models/nonexistent\n"
    found = inventory.find_on_disk(inventory.parse_extra_paths(yaml))
    assert [Path(p).name for p in found["seedvr2_3b_int8_convrot.safetensors"]] == ["seedvr2_3b_int8_convrot.safetensors"]
    assert [Path(p).name for p in found["seedvr2_ema_vae_fp16.safetensors"]] == ["ema_vae_fp16.safetensors"]
    assert found["flux2-vae.safetensors"] == [] and found["Moss\\lora_dmd2.safetensors"] == []       # a folder that does not exist is no error
    assert set(found) == set(manifest.FILES)


def main():
    test_manifest()
    test_workflows_covered()
    test_resolve()
    test_status()
    test_rows_and_texts()
    test_graph_names()
    test_comfy_reading()
    test_settings()
    test_extra_paths()
    test_find_on_disk()
    print("ok")


if __name__ == "__main__":
    main()
