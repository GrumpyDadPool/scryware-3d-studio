"""
Scryware 3D Studio - WSL-side TRELLIS.2 runner.

Runs INSIDE WSL in the trellis2 conda env. Called by the Windows GUI via:
    wsl -e bash -lic "conda run -n trellis2 python run_trellis.py <in> <out> [--pipeline-type 512] [--seed 42]"

Progress: prints STAGE markers to stdout; tqdm bars go to stderr (both streamed to GUI).
On success prints: DONE: <output path>
"""
import os
import sys
import argparse

# Must be set before trellis2 is imported (selects torch SDPA attention,
# no flash_attn / xformers needed). See patch_sdpa.py.
os.environ["ATTN_BACKEND"] = "sdpa"


def log(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_image")
    ap.add_argument("output_glb")
    ap.add_argument("--pipeline-type", default="512", choices=["512", "1024", "1024_cascade", "1536_cascade"])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    log("STAGE: loading")
    log("Loading TRELLIS.2 pipeline (first run downloads weights)...")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.to("cuda")

    log("STAGE: generating")
    log(f"Input: {args.input_image}")
    image = Image.open(args.input_image)

    meshes = pipeline.run(
        image,
        pipeline_type=args.pipeline_type,
        seed=args.seed,
    )
    mesh = meshes[0]

    log("STAGE: exporting")
    log(f"Exporting to {args.output_glb}")
    mesh.export(args.output_glb)

    # Report stats for the GUI
    try:
        verts = len(mesh.vertices)
        faces = len(mesh.faces)
        log(f"STATS: vertices={verts} faces={faces}")
    except Exception:
        pass

    log(f"DONE: {args.output_glb}")


if __name__ == "__main__":
    main()
