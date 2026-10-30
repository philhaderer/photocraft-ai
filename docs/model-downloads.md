# Model downloads (direct links)

Checked on 2026-10-27. Every link points straight at the file. For each one the size the server reports matches the
user's working copy byte for byte. Where the name alone was not unique (the DMD2 LoRA, the two Civitai LoRAs, the
FLUX.2 Klein model), the SHA256 of the working copy was matched too. Nothing was downloaded for the check.
`pccomfy/manifest.py` holds the same links (field `url`, `size`, `note`); the settings window (gear) shows them for
missing files.

**Gated** = the file needs a Hugging Face login and accepting the licence on the model page first; the direct link
answers "401" until then.

| File | Folder (ComfyUI\models\...) | Size | Source | Licence | Gated |
|---|---|---|---|---|---|
| flux3-image-klein-int8-convrot.safetensors | diffusion_models | 5.8 GB | [black-forest-labs/flux-3-image-klein-comfy](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/resolve/main/diffusion_models/flux3-image-klein-int8-convrot.safetensors) | FLUX Kommunity License | yes |
| flux-2-klein-9b_int8_convrot.safetensors | diffusion_models | 9.4 GB | [obsxrver/ComfyUI-Native-INT8_ConvRot](https://huggingface.co/obsxrver/ComfyUI-Native-INT8_ConvRot/resolve/main/diffusion_models/flux-2-klein-9b_int8_convrot.safetensors) | FLUX non-commercial (upstream FLUX.2 klein 9B) | no |
| qwen_image_2.1_int8_convrot.safetensors | diffusion_models | 7.3 GB | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors) | Qwen research licence | no |
| fibo2_edit_turbo_int8_convrot.safetensors | diffusion_models | 8.4 GB | [Comfy-Org/Fibo-2.0](https://huggingface.co/Comfy-Org/Fibo-2.0/resolve/main/diffusion_models/fibo2_edit_turbo_int8_convrot.safetensors) | CC BY-NC 4.0 (non-commercial) | no |
| krea2_turbo_int8_convrot.safetensors | diffusion_models | 13.5 GB | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_int8_convrot.safetensors) | Krea 2 Community License | no |
| moss_image_sft_int8_convrot.safetensors | diffusion_models | 5.4 GB | [Comfy-Org/MOSS-Image](https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/diffusion_models/moss_image_sft_int8_convrot.safetensors) | Apache 2.0 | no |
| seedvr2_3b_int8_convrot.safetensors | diffusion_models | 3.5 GB | [Comfy-Org/SeedVR2](https://huggingface.co/Comfy-Org/SeedVR2/resolve/main/diffusion_models/seedvr2_3b_int8_convrot.safetensors) | Apache 2.0 | no |
| qwen_3_8b_fp8mixed.safetensors | text_encoders | 8.7 GB | [Comfy-Org/Flux-2-Klein-9B](https://huggingface.co/Comfy-Org/Flux-2-Klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors) | repo: FLUX non-commercial | no |
| qwen3vl_4b_int8_convrot.safetensors | text_encoders | 4.9 GB | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_int8_convrot.safetensors) (also Fibo-2.0, FLUX.3 Klein) | repo: Krea 2 Community | no |
| qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors | text_encoders | 6.7 GB | [black-forest-labs/flux-3-image-klein-comfy](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/resolve/main/text_encoders/qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors) | FLUX Kommunity License | yes |
| qwen3vl_8b_fp8_scaled.safetensors | text_encoders | 10.6 GB | [Comfy-Org/Qwen3-VL](https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors) | Apache 2.0 | no |
| qwen3vl_8b_int8_convrot.safetensors | text_encoders | 9.4 GB | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors) (also Qwen3-VL) | Apache 2.0 | no |
| qwen3.5_9b_w4a8_gptq.safetensors | text_encoders | 7.3 GB | [Comfy-Org/MOSS-Image](https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/text_encoders/qwen3.5_9b_w4a8_gptq.safetensors) | Apache 2.0 | no |
| qwen3.5_9b_int8_convrot.safetensors | text_encoders | 9.7 GB | [Comfy-Org/MOSS-Image](https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/text_encoders/qwen3.5_9b_int8_convrot.safetensors) | Apache 2.0 | no |
| qwen3vl_4b_fp8_scaled.safetensors | text_encoders | 5.2 GB | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors) (also Qwen3-VL) | Apache 2.0 | no |
| flux2-vae.safetensors | vae | 336 MB | [Comfy-Org/Flux-2-Dev](https://huggingface.co/Comfy-Org/Flux-2-Dev/resolve/main/split_files/vae/flux2-vae.safetensors) | repo: FLUX dev non-commercial | no |
| flux2-vae_small.safetensors | vae | 250 MB | [Comfy-Org/MOSS-Image](https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/vae/flux2-vae_small.safetensors) | Apache 2.0 | no |
| qwen_image_2.1_vae_bf16.safetensors | vae | 676 MB | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/vae/qwen_image_2.1_vae_bf16.safetensors) | Qwen research licence | no |
| qwen_image_vae.safetensors | vae | 254 MB | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/vae/qwen_image_vae.safetensors) (also Qwen-Image) | repo: Krea 2 Community | no |
| seedvr2_ema_vae_fp16.safetensors | vae | 501 MB | [Comfy-Org/SeedVR2](https://huggingface.co/Comfy-Org/SeedVR2/resolve/main/vae/seedvr2_ema_vae_fp16.safetensors) | Apache 2.0 | no |
| qwen\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors | loras\qwen | 913 MB | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/loras/qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors) | Qwen research licence | no |
| Flux 2\ultra_real_v4.safetensors | loras\Flux 2 | 166 MB | [Civitai 2462105, version KL9_V4](https://civitai.com/api/download/models/2846977) (vizsumit) | Civitai: commercial use and derivatives allowed, no credit needed | Civitai may ask to log in |
| Moss\lora_dmd2.safetensors | loras\Moss | 1.2 GB | [lodestones/MOSS-Image-Base-8-steps-dmd](https://huggingface.co/lodestones/MOSS-Image-Base-8-steps-dmd/resolve/main/lora_dmd2.safetensors) | Apache 2.0 | no |
| Moss\lenovo_moss.safetensors | loras\Moss | 65 MB | [Danrisi/lenovo_moss](https://huggingface.co/Danrisi/lenovo_moss/resolve/main/lenovo_moss.safetensors) (also Civitai 1662740) | HF: Apache 2.0; Civitai: credit required, no derivatives | no |
| Flux 3\flux-3-image-klein-restore.safetensors | loras\Flux 3 | 161 MB | [ausboss/FLUX-3-Image-Klein-Restore-LoRA](https://huggingface.co/ausboss/FLUX-3-Image-Klein-Restore-LoRA/resolve/main/flux-3-image-klein-restore.safetensors) (added 30.10., size matches the user's copy) | FLUX Kommunity License | no |
| birefnet.safetensors | background_removal | 444 MB | [Comfy-Org/BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors) (added 30.10., size matches the user's copy) | MIT | no |

## Findings

- **FLUX.2 Klein 9B (int8 ConvRot)**: the old file (`flux-2-klein-9b-int8-ConvRot-comfyui.safetensors`, Sakujo repo) has
  no public source any more (401). Since 2026-10-27 the plugin uses obsxrver's build instead
  (`flux-2-klein-9b_int8_convrot.safetensors`, 9 439 894 544 bytes, SHA256 bd041cec…, the same on `main` and at commit
  d225df1). It is a different conversion (425 instead of 429 tensors, BFL names, 112 int8 layers) but an A/B test with
  the plugin's own workflows (`tests/live_flux2_file_compare.py`: Text to image, Edit, Refine, two seeds each) gave the
  same pictures with small differences in fine detail (PSNR 27 to 41 dB) at the same speed. The old file can still be
  used through the settings window (own file instead of the expected one, once that exists).
- **DMD2 LoRA for MOSS**: the user's `lora_dmd2.safetensors` is the file of that name in
  `lodestones/MOSS-Image-Base-8-steps-dmd` (same SHA256, also in `lodestones/Kromoss`), not the `lora.safetensors` of
  the SFT repo that the manifest guessed before.
- **flux2-vae**: the copy in `Comfy-Org/Flux-2-Dev` is byte-identical with the user's; the copies in the Klein, MOSS,
  Fibo and FLUX.3 repos are 2264 bytes smaller (a different file header) and load the same way.
- **Licences for the release**: Fibo 2.0 (CC BY-NC) and the FLUX.2 files are non-commercial; Lenovo UltraReal on
  Civitai asks for credit (name Danrisi in the credits).
