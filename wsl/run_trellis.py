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
    ap.add_argument("--decimation-target", type=int, default=1000000,
                    help="Target face count for the output mesh")
    ap.add_argument("--texture-size", type=int, default=4096,
                    help="Texture resolution (1024, 2048, 4096)")
    ap.add_argument("--no-remesh", action="store_true",
                    help="Skip remeshing (faster, rougher topology)")
    args = ap.parse_args()

    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    log("STAGE: loading")
    log("Loading TRELLIS.2 pipeline (weights cached after first run)...")
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

    # MeshWithVoxel -> GLB via o_voxel (official TRELLIS.2 export path)
    import o_voxel
    try:
        mesh.simplify(16777216)  # nvdiffrast limit, per official example
    except Exception:
        pass
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=args.decimation_target,
        texture_size=args.texture_size,
        remesh=not args.no_remesh,
        remesh_band=1,
        remesh_project=0,
        verbose=True,
    )
    glb.export(args.output_glb, extension_webp=True)

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
