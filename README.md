# Scryware 3D Studio (v1)

Windows GUI for the local 3D asset pipeline. No terminal needed:

1. **Generate 3D** — pick an image, TRELLIS.2 builds a textured `.glb` in WSL2
2. **Rig** — SkinTokens auto-rigging in WSL2
3. **Animate** — embedded Mixamo browser, downloads go to your project folder

## Install (Windows)

```powershell
# Python 3.10+ required
pip install -r requirements.txt
```

Prerequisites (one-time, already done if you followed the setup guide):
- WSL2 + Ubuntu with TRELLIS.2 working (`conda env 'trellis2'`, repo at `~/miniconda3/TRELLIS.2`, SDPA patch applied)
- WSL2 memory at 24 GB (WSL Settings) — 16 GB gets OOM-killed on the 1024 cascade

## Run

```powershell
python main.py
```

## How it works

The app runs on Windows and remote-controls WSL via `wsl.exe`:
- Your image picker / output folder are normal Windows dialogs
- On Generate, the app deploys `wsl/run_trellis.py` into WSL and runs it in the
  `trellis2` conda env, streaming the log back live
- Windows paths are translated to `/mnt/c/...` automatically
- The finished `.glb` lands directly in your Windows output folder

## Tabs

**1. Generate 3D** — input image, quality (Fast 512 / High 1024 cascade), seed.
Progress bar tracks the pipeline stages. When done: show in folder, open in
Blender, preview in browser, or send straight to the Rig tab.

**2. Rig** — checks for `~/SkinTokens` in WSL. If it's not installed yet, the tab
shows setup guidance instead of failing. Once installed: pick a `.glb`, rig it.

**3. Animate** — Chromium browser pointed at mixamo.com, embedded in the app.
Log in once, upload your rigged character (FBX), pick animations, download —
files land in your output folder automatically.

## Notes / limits (v1)

- Mixamo upload is manual in v1 (click through their UI in the embedded browser).
  One-click upload from the app is planned.
- No embedded 3D viewport yet — use "Preview in browser" or Blender.
- SkinTokens wiring uses a configurable command template (`RIG_CMD_TEMPLATE`
  in `gui/rig_tab.py`) — adjusted once SkinTokens is installed and its CLI confirmed.
- The app auto-detects your WSL distro (prefers Ubuntu-22.04, then Ubuntu).

## Project layout

```
scryware-3d-studio/
  main.py                 # entry point (Windows)
  requirements.txt
  backend/
    wsl_bridge.py         # wsl.exe wrapper, path translation, file deploy
  gui/
    main_window.py        # tab shell
    generate_tab.py       # image -> TRELLIS.2 -> .glb
    rig_tab.py            # .glb -> SkinTokens
    animate_tab.py        # embedded Mixamo browser
  wsl/
    run_trellis.py        # deployed into WSL, runs the actual pipeline
```
