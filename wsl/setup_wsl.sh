#!/usr/bin/env bash
# Scryware 3D Studio - WSL environment setup.
# Run inside WSL2 Ubuntu 22.04 (called by install.ps1 on Windows).
# Idempotent: safe to re-run; skips steps that are already done.
set -euo pipefail

echo "=== Scryware 3D Studio WSL setup ==="
echo "This installs: miniconda, TRELLIS.2 (conda env 'trellis2'),"
echo "SkinTokens (venv at ~/SkinTokens), and all GPU dependencies."
echo "Expect 30-60 minutes and ~35 GB of downloads."
echo ""

# ---------- system packages ----------
echo "--- system packages (needs sudo) ---"
sudo apt update
sudo apt install -y git wget curl \
    libsm6 libice6 libxext6 libxrender1 libxi6 libgl1 libglib2.0-0

# ---------- miniconda ----------
if [ ! -d "$HOME/miniconda3" ]; then
    echo "--- installing miniconda ---"
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
        -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
    rm /tmp/miniconda.sh
else
    echo "--- miniconda already installed ---"
fi
export PATH="$HOME/miniconda3/bin:$PATH"
# shellcheck disable=SC1091
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || true

# ---------- TRELLIS.2 ----------
if [ ! -d "$HOME/miniconda3/TRELLIS.2" ]; then
    echo "--- cloning TRELLIS.2 ---"
    git clone --recurse-submodules https://github.com/microsoft/TRELLIS.2 \
        "$HOME/miniconda3/TRELLIS.2"
else
    echo "--- TRELLIS.2 already cloned ---"
fi

if ! conda env list | grep -q "^trellis2 "; then
    echo "--- creating conda env 'trellis2' ---"
    conda create -n trellis2 python=3.10 -y
else
    echo "--- conda env 'trellis2' exists ---"
fi

echo "--- TRELLIS.2 dependencies ---"
conda run -n trellis2 pip install --upgrade pip
# PyTorch with CUDA 12.4 (matches the validated working setup)
conda run -n trellis2 pip install torch==2.6.0 torchvision==0.21.0 \
    --index-url https://download.pytorch.org/whl/cu124
# Real nvcc (the pip nvidia-cuda-nvcc wheel ships ptxas but no nvcc binary)
conda install -n trellis2 -c "nvidia/label/cuda-12.4.0" cuda-nvcc -y
# TRELLIS.2 requirements (xformers intentionally skipped: wrong build, unused)
conda run -n trellis2 pip install -r "$HOME/miniconda3/TRELLIS.2/requirements.txt" \
    || echo "WARNING: requirements install had errors, continuing"

# SDPA sparse-attention patch (replaces flash_attn/xformers need)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "--- applying SDPA attention patch ---"
conda run -n trellis2 python "$SCRIPT_DIR/patch_sdpa.py"

# DINOv3 compat fix: self.model.layer -> self.model.model.layer
echo "--- applying DINOv3 compat fix ---"
DINO_FILE=$(conda run -n trellis2 python -c \
    "import trellis2, os; print(os.path.dirname(trellis2.__file__))" \
    2>/dev/null)/models/dinov3.py 2>/dev/null || true
if [ -n "${DINO_FILE:-}" ] && [ -f "$DINO_FILE" ]; then
    if grep -q "self\.model\.layer" "$DINO_FILE" \
        && ! grep -q "self\.model\.model\.layer" "$DINO_FILE"; then
        sed -i 's/self\.model\.layer/self.model.model.layer/g' "$DINO_FILE"
        echo "patched $DINO_FILE"
    else
        echo "DINOv3 fix already applied or not needed"
    fi
else
    echo "WARNING: could not locate dinov3.py, skipping DINO fix"
fi

# ---------- SkinTokens ----------
if [ ! -d "$HOME/SkinTokens" ]; then
    echo "--- cloning SkinTokens ---"
    git clone https://github.com/GrumpyDadPool/SkinTokens "$HOME/SkinTokens" \
        || git clone https://github.com/facebookresearch/SkinTokens \
            "$HOME/SkinTokens" 2>/dev/null \
        || echo "WARNING: SkinTokens clone failed, skipping"
else
    echo "--- SkinTokens already cloned ---"
fi

if [ -d "$HOME/SkinTokens" ]; then
    echo "--- SkinTokens venv ---"
    if [ ! -d "$HOME/SkinTokens/.venv" ]; then
        python3.11 -m venv "$HOME/SkinTokens/.venv" \
            || python3 -m venv "$HOME/SkinTokens/.venv"
    fi
    VPY="$HOME/SkinTokens/.venv/bin/python"
    "$VPY" -m pip install --upgrade pip
    # PyTorch with CUDA 12.8
    "$VPY" -m pip install torch==2.7.0 torchvision==0.22.0 \
        --index-url https://download.pytorch.org/whl/cu128
    # Prebuilt flash-attn wheel (no local nvcc build needed)
    "$VPY" -m pip install flash-attn==2.8.3.post1 --no-build-isolation
    # requirements.txt omits scipy upstream
    "$VPY" -m pip install -r "$HOME/SkinTokens/requirements.txt" scipy \
        || echo "WARNING: SkinTokens requirements had errors, continuing"
    echo "--- SkinTokens test (bundled giraffe) ---"
    if "$VPY" "$HOME/SkinTokens/demo.py" \
        --input "$HOME/SkinTokens/examples/giraffe.glb" \
        --output /tmp/giraffe_rigged.glb --use_transfer 2>&1 | tail -3; then
        echo "SkinTokens smoke test passed"
    else
        echo "WARNING: SkinTokens smoke test failed — check manually"
    fi
fi

echo ""
echo "=== WSL setup complete ==="
echo "TRELLIS.2: conda env 'trellis2', repo at ~/miniconda3/TRELLIS.2"
echo "SkinTokens: venv at ~/SkinTokens/.venv"
echo "Back on Windows, run:  pip install -r requirements.txt  &&  python main.py"
