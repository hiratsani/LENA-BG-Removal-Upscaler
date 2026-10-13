"""Conservative, fail-safe finishing for LENA outputs.

The functions in this module never own model inference.  They only polish an
already valid result and deliberately return the input when a refinement is
unsafe or cannot be completed.
"""

from PIL import Image, ImageChops, ImageFilter


PROFILES = {
    "general": {"blur": 0.55, "blend": 72, "cleanup": True, "spill": 0.18},
}
MAX_FINISH_PIXELS = 8_000_000


def _profile(name):
    return PROFILES.get(name, PROFILES["general"])


def finish_alpha(alpha, profile="general"):
    """Polish only uncertain edge pixels and isolated one-pixel artifacts."""
    try:
        import numpy as np

        alpha = alpha.convert("L")
        if alpha.width * alpha.height > MAX_FINISH_PIXELS:
            return alpha
        values = np.asarray(alpha).copy()
        if values.size == 0:
            return alpha

        # Remove only true single-pixel specks/pinholes. Requiring eight direct
        # neighbours for filling and <=1 for removal protects lines and hair.
        hard = values >= 248
        padded = np.pad(hard, 1, mode="edge")
        neighbours = np.zeros(hard.shape, dtype=np.uint8)
        for dy, dx in (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            neighbours += padded[
                1 + dy : 1 + dy + hard.shape[0], 1 + dx : 1 + dx + hard.shape[1]
            ]
        if _profile(profile)["cleanup"]:
            values[hard & (neighbours <= 1)] = 0
            values[(values <= 7) & (neighbours == 8)] = 255
        else:
            values[hard & (neighbours == 0)] = 0

        base = Image.fromarray(values, "L")
        settings = _profile(profile)
        smooth = base.filter(ImageFilter.GaussianBlur(settings["blur"]))
        uncertain = Image.fromarray(
            np.where((values > 5) & (values < 250), settings["blend"], 0).astype(
                "uint8"
            ),
            "L",
        ).filter(ImageFilter.MaxFilter(3))
        return Image.composite(smooth, base, uncertain)
    except Exception:
        return alpha.convert("L")


def finish_cutout(original, alpha, profile="general"):
    """Apply a finished alpha while preserving source RGB and transparency."""
    try:
        result = original.convert("RGBA").copy()
        source_alpha = result.getchannel("A")
        polished = finish_alpha(
            alpha.resize(result.size, Image.Resampling.LANCZOS), profile
        )
        result.putalpha(ImageChops.multiply(source_alpha, polished))
        return reduce_edge_spill(result, profile)
    except Exception:
        result = original.convert("RGBA").copy()
        result.putalpha(
            ImageChops.multiply(
                result.getchannel("A"), alpha.convert("L").resize(result.size)
            )
        )
        return result


def reduce_edge_spill(result, profile="general"):
    """Borrow nearby opaque foreground colour for a small soft-edge dehalo."""
    try:
        import numpy as np

        if result.width * result.height > 2_000_000:
            return result
        rgba = result.convert("RGBA")
        alpha = np.asarray(rgba.getchannel("A"))
        rgb = np.asarray(rgba.convert("RGB")).copy()
        known = alpha >= 238
        if not known.any():
            return result
        propagated = rgb.astype(np.float32)
        height, width = alpha.shape
        for _ in range(3):
            total = np.zeros((height, width, 3), dtype=np.float32)
            count = np.zeros((height, width), dtype=np.uint8)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ys = slice(max(0, dy), min(height, height + dy))
                yd = slice(max(0, -dy), min(height, height - dy))
                xs = slice(max(0, dx), min(width, width + dx))
                xd = slice(max(0, -dx), min(width, width - dx))
                valid = known[ys, xs]
                total[yd, xd] += propagated[ys, xs] * valid[..., None]
                count[yd, xd] += valid
            fill = (~known) & (count > 0)
            if not fill.any():
                break
            propagated[fill] = total[fill] / count[fill, None]
            known |= fill
        edge = (alpha > 0) & (alpha < 230) & known
        if not edge.any():
            return result
        strength = _profile(profile)["spill"]
        rgb[edge] = (
            np.rint(rgb[edge] * (1 - strength) + propagated[edge] * strength)
            .clip(0, 255)
            .astype("uint8")
        )
        output = Image.fromarray(rgb, "RGB")
        output.putalpha(rgba.getchannel("A"))
        return output
    except Exception:
        return result


def validate_alpha(alpha):
    """Return a cheap, deliberately high-confidence bad-mask assessment."""
    try:
        import numpy as np

        values = np.asarray(alpha.convert("L"))
        if values.size == 0 or not np.isfinite(values).all():
            return {"warning": True, "reason": "invalid-alpha"}
        visible = values > 12
        coverage = float(visible.mean())
        if int(values.max()) <= 8 or coverage < 0.00025:
            return {"warning": True, "reason": "almost-empty", "coverage": coverage}
        border = np.concatenate(
            (visible[0], visible[-1], visible[:, 0], visible[:, -1])
        )
        border_coverage = float(border.mean())
        if coverage > 0.9992 and border_coverage > 0.995:
            return {"warning": True, "reason": "almost-full", "coverage": coverage}
        return {"warning": False, "coverage": coverage, "border": border_coverage}
    except Exception:
        return {"warning": False, "reason": "validation-unavailable"}


def finish_upscale(result):
    """Apply a tiny amount of bounded sharpening; skip very large outputs."""
    try:
        if result.width * result.height > 12_000_000:
            return result
        rgba = result.convert("RGBA")
        alpha = rgba.getchannel("A")
        rgb = rgba.convert("RGB")
        # Only high local deviations receive a tiny median blend. Flat areas,
        # skin gradients and existing detail remain untouched.
        median = rgb.filter(ImageFilter.MedianFilter(3))
        noise = (
            ImageChops.difference(rgb, median)
            .convert("L")
            .point(lambda value: max(0, min(24, (value - 12) * 2)))
        )
        rgb = Image.composite(median, rgb, noise)
        sharpened = rgb.filter(
            ImageFilter.UnsharpMask(radius=0.65, percent=24, threshold=5)
        )
        rgb = Image.blend(rgb, sharpened, 0.22)
        rgb.putalpha(alpha)
        return rgb
    except Exception:
        return result
