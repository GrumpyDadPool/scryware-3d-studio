import os
TRELLIS_DIR = os.path.expanduser("~/miniconda3/TRELLIS.2")
"""DINOv3 compat fix for TRELLIS.2's image feature extractor.

The installed transformers build nests the DINOv3 encoder one level deeper
than the attribute path TRELLIS.2 was written against, so
DinoV3FeatureExtractor crashes on its layer loop. One-line change in
trellis2/modules/image_feature_extractor.py:
    enumerate(self.model.layer) -> enumerate(self.model.model.layer)
Idempotent: safe to re-run. (This is the fix the live WSL checkout runs
with; see trellis2-local-patches.diff for the exact live diff. The old
setup_wsl.sh sed targeted trellis2/models/dinov3.py, which does not
exist in TRELLIS.2, so it never applied anything.)
"""

p = TRELLIS_DIR + "/trellis2/modules/image_feature_extractor.py"
src = open(p).read()

if "self.model.model.layer" in src:
    print("image_feature_extractor.py already patched, skipping")
elif "enumerate(self.model.layer)" in src:
    src = src.replace(
        "enumerate(self.model.layer)", "enumerate(self.model.model.layer)"
    )
    open(p, "w").write(src)
    import py_compile

    py_compile.compile(p, doraise=True)
    print("patched image_feature_extractor.py (compiles clean)")
else:
    raise AssertionError(
        "could not find the DINOv3 layer loop in image_feature_extractor.py"
    )
