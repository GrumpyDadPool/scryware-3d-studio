"""
Scryware 3D Studio - machine profile reader.

install.ps1 probes the PC it runs on (RAM, CPU, GPU/VRAM) and writes
machine-profile.json next to main.py with sizing for WSL and a
recommended Generate quality for that hardware. This module reads it.

The profile is per-machine generated state: it is gitignored and never
committed. A missing or unreadable profile is normal (manual installs)
and simply means "use the built-in defaults".
"""
import json
import os

PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "machine-profile.json",
)

# Must match the quality combo's item data in gui/generate_tab.py.
VALID_QUALITIES = {"512", "1024", "1024_cascade", "1536_cascade"}


def load_profile():
    """Return the machine profile dict, or None if absent/unreadable."""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def recommended_quality():
    """Return the profile's Generate quality, validated, or None."""
    profile = load_profile()
    if not profile:
        return None
    quality = profile.get("recommended_quality")
    return quality if quality in VALID_QUALITIES else None
