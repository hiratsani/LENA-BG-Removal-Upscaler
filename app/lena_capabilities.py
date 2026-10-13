"""Conservative DirectML policy for the pinned model exports shipped by LENA.

See GPU-AUDIT.md. CPU policy does not imply architecture-wide GPU incompatibility.
"""

GPU_MODELS = frozenset()


def gpu_supported(model):
    return model in GPU_MODELS


def mode_label(model, language="en"):
    import sys

    if sys.platform == "darwin":
        return "CPU Mode · macOS"
    if gpu_supported(model):
        return "GPU Mode Supported"
    return (
        "CPU Mode · GPU belum terverifikasi"
        if language == "id"
        else "CPU Mode · GPU not verified"
    )
