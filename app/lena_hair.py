"""ViTMatte INT8 refinement using the selected quality's alpha as a trimap.

Pinned Xenova export: RGB normalized to [-1,1], trimap in [0,1], then
zero-pad all four channels on the right/bottom to a multiple of 32.
"""

import numpy as np
from PIL import Image, ImageFilter, ImageChops

MAX_EDGE = 1024


def prepare_inputs(original, alpha):
    factor = min(1, MAX_EDGE / max(original.size))
    width = max(1, round(original.width * factor))
    height = max(1, round(original.height * factor))
    mask = alpha.convert("L").resize((width, height), Image.Resampling.LANCZOS)
    foreground = np.asarray(mask.filter(ImageFilter.MinFilter(15))) >= 248
    background = np.asarray(mask.filter(ImageFilter.MaxFilter(15))) <= 7
    trimap = np.full((height, width), 128, dtype=np.uint8)
    trimap[foreground] = 255
    trimap[background] = 0
    rgb = (
        np.asarray(
            original.convert("RGB").resize((width, height), Image.Resampling.BILINEAR),
            dtype=np.float32,
        )
        / 255
    )
    rgb = (rgb - 0.5) / 0.5
    tensor = np.concatenate(
        (rgb.transpose(2, 0, 1), trimap[None].astype(np.float32) / 255), axis=0
    )
    tensor = np.pad(
        tensor, ((0, 0), (0, (-height) % 32), (0, (-width) % 32)), mode="constant"
    )[None]
    return tensor, trimap


def refine_hair(original, alpha):
    from lena_models import path, REFINER

    source = path(REFINER)
    if source is None:
        raise IOError("ViTMatte Hair & Fur model is not available")
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.enable_cpu_mem_arena = False
    session = ort.InferenceSession(
        str(source), sess_options=options, providers=["CPUExecutionProvider"]
    )
    meta = session.get_inputs()[0]
    if (
        len(session.get_inputs()) != 1
        or len(meta.shape) != 4
        or meta.name != "pixel_values"
        or meta.type != "tensor(float)"
    ):
        raise ValueError("Unexpected ViTMatte input contract")
    tensor, trimap = prepare_inputs(original, alpha)
    height, width = trimap.shape
    raw = session.run(["alphas"], {meta.name: tensor})[0]
    if (
        raw.shape != (1, 1, tensor.shape[2], tensor.shape[3])
        or not np.isfinite(raw).all()
    ):
        raise ValueError("Invalid refined alpha")
    pred = np.clip(raw[0, 0, :height, :width], 0, 1)
    pred[trimap == 255] = 1
    pred[trimap == 0] = 0
    refined = Image.fromarray(np.rint(pred * 255).astype(np.uint8)).resize(
        original.size, Image.Resampling.LANCZOS
    )
    result = original.convert("RGBA").copy()
    result.putalpha(ImageChops.multiply(result.getchannel("A"), refined))
    return result
