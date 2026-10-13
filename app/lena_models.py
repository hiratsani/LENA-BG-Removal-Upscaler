"""Universal removal qualities and persistent model availability."""

import json
from lena_config import ROOT, CACHE

MANIFEST = json.loads((ROOT / "assets/models.json").read_text(encoding="utf-8"))
QUALITIES = (
    ("isnet-general", "Basic"),
    ("birefnet-lite", "Better"),
    ("mvanet", "Best"),
)
REFINER = "vitmatte-small"
MODELS = {
    "isnet-general": (
        "IS-Net General INT8",
        "Hasil cepat, ringan di perangkat.",
        "Quick results, light on your device.",
        1024,
        "isnet",
    ),
    "birefnet-lite": (
        "BiRefNet Lite FP16",
        "Lebih detail, performa seimbang.",
        "More detail, balanced performance.",
        1024,
        "logits",
    ),
    "mvanet": (
        "MVANet INT8",
        "Detail maksimal, memakai lebih banyak sumber daya.",
        "Maximum detail, uses more resources.",
        1024,
        "alpha",
    ),
    REFINER: (
        "ViTMatte Small INT8",
        "Refinement rambut dan bulu.",
        "Hair and fur refinement.",
        512,
        "matting",
    ),
    "span": (
        "SPAN",
        "Perbesar foto dengan model universal yang ringan",
        "Enlarge photos with a lightweight universal model",
        128,
        "upscale",
    ),
}


def folder(name):
    return CACHE / name


def path(name):
    if name not in MODELS:
        return None
    if name in ("span", "isnet-general", REFINER):
        bundled = (
            ROOT
            / "assets"
            / {
                "span": "span.onnx",
                "isnet-general": "isnet-general-int8.onnx",
                REFINER: "vitmatte-small-int8.onnx",
            }[name]
        )
        if bundled.is_file() and bundled.stat().st_size == MANIFEST[name]["size"]:
            return bundled
        if name == "isnet-general":
            return None
    target = folder(name) / "model.onnx"
    try:
        ready = json.loads((folder(name) / "ready.json").read_text())
        meta = MANIFEST[name]
        if (
            meta.get("hash")
            and ready.get("hash") == meta["hash"]
            and target.stat().st_size == meta["size"]
        ):
            return target
    except (OSError, ValueError, KeyError):
        pass
    return None


def size(name):
    return MANIFEST[name]["size"]


def size_text(name):
    n = size(name)
    return f"{n/1e6:.1f} MB" if n < 10_000_000 else f"{n/1e6:.0f} MB"


def saved_quality(settings):
    name = settings.get("quality", "isnet-general")
    return name if name in dict(QUALITIES) and path(name) else "isnet-general"
