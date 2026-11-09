# Samples

Three finished Generate outputs from the Doomsday Tycoon cast run
(Oct-Nov 2026), so a new install has something to check itself against.

The input images are in this folder. The matching `.glb` outputs are
35-37 MB each, too big for the repo, so they ride in the v1.0 release zip
under `samples/glb/`. Open one next to its concept image: proportions,
silhouette, and the face should read true to the concept at turntable
distance. Texture detail on the back is the model's guess, same as any
single-image run.

All three used pipeline type 512 and seed 42, the settings the whole cast
run standardized on.

## Gus: `gus-concept.png` → `gus.glb`

The pipeline proof, 2026-11-06. The concept was generated from Gus's
locked portrait: front view, A-pose, smooth painted style, white
background. Output came out at about 695k verts / 1.44M faces, textured.
SkinTokens then rigged it (49 bones) and the weights were transferred
back onto this textured mesh in Blender at 100% coverage. Start here:
if your install reproduces a mesh of this quality from this image, the
pipeline is healthy.

## Brick: `brick-concept.png` → `brick.glb`

Approved cast model, 2026-11-06. SkinTokens rig: 28 bones. This is the
character whose working file grew a floating shell artifact beside her
face (a layered TRELLIS patch cluster). It was removed in Blender with
screen-coverage deletion and verified gone with an alpha-component scan
of the turntable. If your own outputs grow floating patches, see
Troubleshooting in the README before reaching for island selection: it
does not catch these.

## Marla v2: `marla2-concept.png` → `marla2.glb`

The redo. The first Marla concept had drifted away from her art, so the
v2 concept was drawn from her original art instead, and the model was
rebuilt from it. Same cast pipeline. The mesh picked up green mossy
patches on the suit during conversion; noted on review and accepted.
The lesson is written up in `docs/game-ready-pipeline-spec.md`
(Production update): build the concept from the character's locked art,
not from a text description of them.
