# Scryware 3D Studio (v1)

Windows GUI for a fully local 3D asset pipeline. No cloud, no fees, no terminal needed:

1. **Generate 3D** — pick an image, TRELLIS.2 builds a textured `.glb` in WSL2
2. **Rig** — SkinTokens auto-rigging in WSL2
3. **Animate** — embedded Mixamo browser, downloads go to your project folder

## Quick install (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer **pops up a pre-flight checklist first** — read it. It covers what
gets installed, the hardware you need, and every approval it will ask for.
Nothing runs until you click "Install".

What it does on approval:
1. Ensures WSL2 + Ubuntu-22.04 (may need one reboot on first run)
2. Writes `%USERPROFILE%\.wslconfig` — 24 GB RAM / 8 GB swap for the models
3. Inside WSL: miniconda, `trellis2` conda env, TRELLIS.2 (patched), SkinTokens venv
4. `pip install -r requirements.txt` for the Windows GUI

Then launch:

```powershell
python main.py
```

### What you need before installing

- Windows 10 (21H2+) or 11, 64-bit
- Virtualization enabled in BIOS/UEFI (WSL2 requirement)
- NVIDIA GPU with ~24 GB VRAM (e.g. RTX 4090) + current driver with WSL CUDA support
- ~50 GB free disk space
- Administrator rights (WSL install needs it)
- Stable internet — ~35 GB of downloads (PyTorch, model weights)
- 30-60 minutes
- **HuggingFace account with the gated DINOv3 license accepted**: visit
  https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m
  in your browser and approve the license *before* installing.
  (TRELLIS.2's DINOv3 backbone — the TRELLIS.2 weights themselves are not
  gated.) The weight download fails without this and the error message won't
  tell you why. The installer will ask for your HF token so the download can
  authenticate.
- Optional: [BRIA-RMBG 2.0](https://huggingface.co/briaai/RMBG-2.0) access
  (request it on the model page) — a higher-quality background removal model.
  The app's background removal works out of the box without it.

### Manual install (if you prefer)

<details>
<summary>Click to expand</summary>

**Windows side:**
```powershell
pip install -r requirements.txt
```

**WSL side** (Ubuntu 22.04) — or just run `wsl/setup_wsl.sh` inside WSL:
- `sudo apt install` the X11 libs (see script)
- miniconda, conda env `trellis2` (python 3.10)
- `torch==2.6.0` cu124, `cuda-nvcc` from `nvidia/label/cuda-12.4.0`
- Clone TRELLIS.2, run `wsl/patch_sdpa.py` (SDPA attention, no flash_attn needed),
  apply the DINOv3 fix (`self.model.layer` -> `self.model.model.layer`)
- Clone SkinTokens to `~/SkinTokens`, python 3.11 venv, `torch==2.7.0` cu128,
  `flash-attn==2.8.3.post1`, `scipy`

Set `ATTN_BACKEND=sdpa` — the app handles this automatically.
</details>

## How it works

The app runs on Windows and remote-controls WSL via `wsl.exe`:
- Your image picker / output folder are normal Windows dialogs
- On Generate, the app strips the image background (rembg, composited on white —
  dark subjects on dark backgrounds confuse the model into a flat pancake),
  deploys `wsl/run_trellis.py` into WSL and runs it in the `trellis2` conda env,
  streaming the log back live
- Windows paths are translated to `/mnt/c/...` automatically
- The finished `.glb` lands directly in your Windows output folder

## Tabs

**1. Generate 3D** — input image, quality (Fast 512 / High 1024 cascade), seed,
background-removal toggle. Progress bar tracks the pipeline stages. When done:
show in folder, open in Blender, preview in browser, or send straight to Rig.

**2. Rig** — checks for `~/SkinTokens` in WSL. If it's not installed yet, the tab
shows setup guidance instead of failing. Once installed: pick a `.glb`, rig it.

**3. Animate** — Chromium browser pointed at mixamo.com, embedded in the app.
Log in once, upload your rigged character (FBX), pick animations, download —
files land in your output folder automatically.

## Notes / limits (v1)

- Mixamo upload is manual in v1 (click through their UI in the embedded browser).
- No embedded 3D viewport yet — use "Preview in browser" or Blender.
- Single-image 3D guesses the back of the subject. Try several seeds; for hero
  assets, clean up in Blender from the generated mesh as a starting point.
- The app auto-detects your WSL distro (prefers Ubuntu-22.04, then Ubuntu).

## Project layout

```
scryware-3d-studio/
  main.py                 # entry point (Windows)
  install.ps1             # one-shot installer with pre-flight popup
  requirements.txt
  assets/icon.ico         # app icon
  backend/
    wsl_bridge.py         # wsl.exe wrapper, path translation, file deploy
  gui/
    main_window.py        # tab shell
    generate_tab.py       # image -> TRELLIS.2 -> .glb
    rig_tab.py            # .glb -> SkinTokens
    animate_tab.py        # embedded Mixamo browser
  wsl/
    run_trellis.py        # deployed into WSL, runs the actual pipeline
    setup_wsl.sh          # full WSL env setup (conda, TRELLIS.2, SkinTokens)
    patch_sdpa.py         # SDPA sparse-attention patch for TRELLIS.2
```
