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

## In production

This is the tool that built the Doomsday Tycoon henchman cast as 3D
models (Oct-Nov 2026): Gus first as the pipeline proof, then Brick,
Cipher, Comet, Flare, Marla, Meltdown, Preston, and Spin, plus a Vex
redo built from corrected canon art. The settings that run standardized
on: pipeline type 512, seed 42, and concept art drawn front-on in an
A-pose on white, generated from the character's locked art.

The method notes from that run (working chain, review gates, cleanup
fixes) live in `docs/game-ready-pipeline-spec.md`, Production update
section.

## Samples

`samples/` holds the input images for three finished models (Gus,
Brick, Marla v2). The `.glb` outputs are too big for the repo and ride
in the v1.0 release zip. See `samples/SAMPLES.md` for what to compare
against.

## Notes / limits (v1)

- Mixamo upload is manual in v1 (click through their UI in the embedded browser).
- No embedded 3D viewport yet — use "Preview in browser" or Blender.
- Single-image 3D guesses the back of the subject. Try several seeds; for hero
  assets, clean up in Blender from the generated mesh as a starting point.
- The app auto-detects your WSL distro (prefers Ubuntu-22.04, then Ubuntu).

## Troubleshooting

Real failures from production use, with the fix that worked.

- **Model weights fail to download and the error does not say why.**
  The gated DINOv3 license has not been accepted yet. Accept it on the
  model page first (see "What you need before installing"), then rerun.
- **Generate stalls right after launch.** WSL cold boot takes 10-30s.
  The app warms WSL in the background and keeps the Generate/Rig
  buttons locked until it is ready. Give it a moment.
- **The mesh comes out flat, like a pancake.** Dark subject on a dark
  background. Keep background removal on (it composites on white) and
  prefer light, plain backgrounds in the source art.
- **Floating blobs, discs, or shell patches hover on the mesh.** A
  known TRELLIS artifact: layered shell patches that sit off the
  surface. Fix in Blender by deleting the faces that project onto the
  artifact's area in a render (screen-coverage selection). Island,
  centroid, and depth-band selection all miss these patches. Keep a
  copy of the file before the fix, and verify with an alpha-component
  scan of a turntable render: only the body component should remain.
- **The rigged GLB has no textures and is the wrong size.** That is
  normal SkinTokens output: re-meshed, untextured, normalized to a
  -1..1 cube (2x the TRELLIS export's scale), sometimes with a stray
  Icosphere helper object in it. Delete the helper, scale the textured
  mesh x2, and move the weights onto the textured TRELLIS mesh in
  Blender with a BVH nearest-face barycentric transfer (target: 100%
  coverage). Do not use Blender's Data Transfer modifier for this: it
  can finish with zero weight groups and no error.
- **The character faces the wrong way.** TRELLIS exports are not
  consistently oriented (one cast member sat 9-40 degrees off the
  family profile). Check a neutral-pose render, then correct the
  armature object's Z rotation in Blender. Set the armature's
  rotation_mode to XYZ first: in quaternion mode, euler rotation edits
  are silently dropped on save.
- **"Bad GLB: file size doesn't match" in Blender.** The GLB was still
  being copied when it was opened. Wait for the copy to finish and
  check the final file size before opening it.
- **A backpack or appendage stretches during animation.** Pin its
  vertices rigid to the chest bone (full weight). Fixed Comet's
  life-support backpack this way.
- **Colors drift from the concept art.** Single-image generation
  invents texture detail: a purple blazer came out near-black on one
  model, another suit picked up green mossy patches. If the look
  matters, generate the concept from the character's original art
  instead of a text description, and judge the model against that art.

## Project layout

```
scryware-3d-studio/
  main.py                 # entry point (Windows)
  install.ps1             # one-shot installer with pre-flight popup
  requirements.txt
  assets/icon.ico         # app icon
  samples/                # input images + notes for three finished models
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
