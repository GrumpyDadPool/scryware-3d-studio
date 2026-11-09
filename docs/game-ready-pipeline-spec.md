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

## Production update — Nov 2026

The v1 pipeline has now run a full production pass: the Doomsday
Tycoon henchman cast, built as 3D models on this stack during
Oct-Nov 2026. Gus was the proof run; Brick, Cipher, Comet, Flare,
Marla, Meltdown, Preston, and Spin followed and were approved as base
models, and a Vex redo was built from corrected canon art. This section
records how the chain actually runs in practice, which differs from
the v1 sketch above in one structural way: the rig is never used
directly. Its weights are transferred back onto the textured TRELLIS
mesh, and that mesh is the working asset.

### The chain as actually run

1. **Concept** — generated from the character's locked art: front
   view, A-pose, smooth painted style, plain white background.
2. **Generate** — TRELLIS.2, pipeline type 512, seed 42 (the settings
   the whole cast run standardized on). Textured GLB out, roughly
   700k verts / 1.4M faces at this size.
3. **Rig** — SkinTokens. Treat its output as a weight source only: it
   is re-meshed, untextured, normalized to a -1..1 cube at 2x the
   TRELLIS export scale, and can carry a stray Icosphere helper
   object that needs deleting.
4. **Weight transfer** — in Blender: scale the textured mesh x2 and
   transfer the rig weights onto it with a BVH nearest-face
   barycentric transfer. Gate: 100% vertex weight coverage, verified
   before anything downstream. (Blender's Data Transfer modifier is
   not used: it returned zero groups with no error.)
5. **Review gates** — a 24-frame turntable render per character,
   checked by eye plus an alpha-component scan of every frame for
   detached pieces. Yaw check on a neutral pose (TRELLIS exports are
   not consistently oriented). Cleanup passes as needed, always with
   a pre-fix backup kept beside the working file.
6. **Approval** — the model is judged against the locked concept art,
   not against a text description of the character.

### Standing rules for rendered sets

- **Face-on camera (2026-11-07).** Sprite sets rendered from these
  models are animated from a front camera, not side profile: at app
  size the face and costume details stay legible where a profile goes
  dark. The earlier profile sets are superseded as the form. The
  separate 2D painted sprite program is unaffected.
- **Prop-hand rule (2026-11-06).** A held prop or weapon stays in the
  same hand in every frame and across ranks, unless the animation is
  an explicit hand-off. Every candidate batch carries a prop-hand
  audit in its NOTES.md. Held props are not modeled by TRELLIS; they
  are a separate later pass.

### Iteration lessons

- **Vex.** The first Vex model was built from a text-driven concept
  (a screen-faced hacker with terminal text) and was rejected as Vex:
  it did not match the character. The redo generated its concept
  directly from the rank-portrait art (deep purple hooded robe, face
  fully shadowed) and matched. The rejected model is kept; it may
  serve as a different villain.
- **Marla.** Same failure, same fix: the v1 concept drifted from her
  art, so v2's concept was drawn from the original art and the model
  rebuilt from that.
- Rule of thumb from both: if a model reads wrong, redo the concept
  from the locked art. Do not try to fix identity at the mesh stage.

### Status

As of 2026-11-07, the 3D-rendered animation route is parked by
Kevin's call: the approved models stand as models, and animation work
returned to the 2D sprite program. The Generate and Rig path above is
unchanged and remains how new base models get made. The v2 stages in
this spec (remesh, bake, LOD, normalize) are still the target for
engine-ready meshes; mesh density is the known blocker there, per the
drip-goku review that motivated this spec.

## Open questions for Kevin

1. Target engine(s)? (drives bone naming, units, export preset)
2. Default triangle budget for LOD0?
3. Bone naming convention preference, or is Mixamo-compatible fine?
