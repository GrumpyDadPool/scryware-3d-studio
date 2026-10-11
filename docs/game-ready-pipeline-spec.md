# Game-Ready Pipeline — Milestone Spec

## Objective

One-click path from TRELLIS sculpt to engine-ready character: quad remesh,
detail bake, clean rig, LODs, named bones, Mixamo animations attached.

## Why

Proven by the drip-goku review (Oct 2026): the current pipeline ends at a
983k-face rigged sculpt. That is a high-detail source, not a game asset.
The missing stages are retopology, detail baking, rig normalization, LODs,
and engine export. This milestone closes that gap.

## Current pipeline (v1)

1. **Generate** — TRELLIS.2 in WSL2 (`wsl/run_trellis.py` via `backend/wsl_bridge.py`)
   → textured GLB. Decimation presets: 25k / 100k / 1M. Remesh toggle on.
2. **Rig** — SkinTokens in WSL2 with `--use_transfer` → rigged GLB.
3. **Animate** — embedded Mixamo browser, manual download to project folder.

## Target pipeline (v2)

### Stage 1 — Quad remesh (Instant Meshes)

- Input: high-poly GLB (Generate or Rig output).
- Tool: Instant Meshes headless binary in WSL.
- Output: quad-dominant mesh at a configurable budget
  (default 40k triangles, range 20k–60k for a third-person PC character).
- Fully automatic; artist touch-up happens at the checkpoint below.

### Stage 2 — Detail bake (Blender headless)

- Input: high-poly source + low-poly retopo mesh.
- `blender --background --python wsl/bake_maps.py`:
  bake normal map and AO from high-poly, transfer base color to the new UVs.
- Output: low-poly GLB + normal / AO textures.
- Note: SkinTokens setup already installs the Blender Linux libs in WSL;
  reuse them, do not install a second Blender.

### Stage 3 — Re-rig (SkinTokens)

- Run the existing rig flow on the retopo'd mesh. A clean mesh produces
  cleaner skin weights than transferring the old rig, so re-rig is the
  default. Rig transfer remains as a fallback option.

### Stage 4 — Normalize (script, `wsl/normalize_rig.py`)

- Bone naming convention (configurable map, default: Mixamo-compatible).
- Scale to real-world units, Y-up, forward axis per engine preset.
- Sanity checks: root bone present, no zero-weight vertices, joint count sane.

### Stage 5 — LOD chain

- LOD0 = retopo mesh; LOD1 ≈ 50%, LOD2 ≈ 25% via scripted decimation.
- Consistent naming (`*_LOD0`, `*_LOD1`, …) plus a metadata sidecar
  for engine import.

### Stage 6 — Animation attach

- No change: existing Animate tab flow (Mixamo download to project folder).

### Stage 7 — Engine export presets

- Unreal: FBX, centimeters, Unreal bone naming.
- Unity: FBX, meters, humanoid-compatible naming.
- Godot / Roblox: GLB as-is.
- Preset selected once in the Game-Ready tab; applied at export.

## Automation boundary (honest)

These stay manual, with GUI checkpoints gating the pipeline:

1. **After remesh** — inspect/fix edge flow around deformation joints
   (shoulders, elbows, hips, knees); separate fused geometry
   (hands, sleeves, torso). No automatic process does this reliably.
2. **After rig** — joint placement and skin-weight QC.
3. **After bake** — texture artifact review (distorted lettering,
   back-side smearing from single-image hallucination).

The pipeline pauses at each checkpoint with a review checklist and resumes
on approval. Everything else runs unattended.

## GUI — new "Game-Ready" tab

- Input picker (defaults to the latest Generate/Rig output).
- Per-stage toggles, triangle budget slider, engine preset dropdown.
- Checkpoint review UI: viewport note + approve/rework buttons.
- Progress streamed per stage through the existing `wsl_bridge` log path.

## New WSL dependencies

- `instant-meshes` headless binary (add to `wsl/setup_wsl.sh`).
- Blender headless: reuse the libs already installed for SkinTokens.

## Milestones (in value order)

- **M1** — Bake + LOD + normalize scripts. No new dependencies beyond what
  exists. Biggest immediate value: usable game meshes from today's sculpts.
- **M2** — Instant Meshes integration + `wsl/remesh_quad.py`.
- **M3** — Game-Ready tab with checkpoint UX wired to `wsl_bridge`.
- **M4** — Engine export presets (Unreal / Unity / Godot-Roblox).

## Open questions for Kevin

1. Target engine(s)? (drives bone naming, units, export preset)
2. Default triangle budget for LOD0?
3. Bone naming convention preference, or is Mixamo-compatible fine?
