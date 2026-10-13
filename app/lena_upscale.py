"""Bounded RGB tile inference; alpha is preserved independently of the RGB model."""

import math
from PIL import Image

MODEL = "span"
MAX_OUTPUT_PIXELS = 64_000_000


def output_size(image, scale):
    if scale not in (2, 4):
        raise ValueError("Scale must be 2 or 4")
    size = (image.width * scale, image.height * scale)
    if size[0] * size[1] > MAX_OUTPUT_PIXELS:
        raise ValueError(
            "Upscale output exceeds 64 megapixels. Choose 2× or a smaller photo."
        )
    return size


def upscale(image, session, scale=4, progress=lambda n, t: None):
    # Only inference needs NumPy; the UI imports output_size at startup.
    import numpy as np

    size = output_size(image, scale)
    # Every invocation has identical dimensions, bounding transformer attention
    # memory and avoiding repeated DirectML graph compilation at image edges.
    tile = 128
    pad = 16
    core = tile - pad * 2
    rgb = image.convert("RGB")
    result = Image.new("RGB", size)
    total = math.ceil(image.width / core) * math.ceil(image.height / core)
    done = 0
    meta = session.get_inputs()[0]
    for y in range(0, image.height, core):
        for x in range(0, image.width, core):
            width = min(core, image.width - x)
            height = min(core, image.height - y)
            left = max(0, x - pad)
            top = max(0, y - pad)
            right = min(image.width, x + core + pad)
            bottom = min(image.height, y + core + pad)
            pixels = (
                np.asarray(rgb.crop((left, top, right, bottom)), dtype=np.float32)
                / 255.0
            )
            pixels = np.pad(
                pixels,
                (
                    (max(0, pad - y), tile - (bottom - top) - max(0, pad - y)),
                    (max(0, pad - x), tile - (right - left) - max(0, pad - x)),
                    (0, 0),
                ),
                mode="edge",
            )
            dtype = (
                np.float16
                if getattr(meta, "type", "") == "tensor(float16)"
                else np.float32
            )
            tensor = np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=dtype)
            output = session.run(None, {meta.name: tensor})[0]
            if (
                output.shape != (1, 3, tile * 4, tile * 4)
                or not np.isfinite(output).all()
            ):
                raise RuntimeError("Unexpected upscale output")
            pixels = np.rint(
                np.clip(
                    output[
                        0, :, pad * 4 : (pad + height) * 4, pad * 4 : (pad + width) * 4
                    ],
                    0,
                    1,
                )
                * 255
            ).astype("uint8")
            patch = Image.fromarray(pixels.transpose(1, 2, 0))
            if scale == 2:
                patch = patch.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
            result.paste(patch, (x * scale, y * scale))
            done += 1
            progress(done, total)
    result.putalpha(image.getchannel("A").resize(size, Image.Resampling.LANCZOS))
    return result
