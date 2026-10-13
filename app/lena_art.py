"""Code-rendered decoration using Hiratsani's supplied font and thunder icon."""

from PIL import Image, ImageDraw, ImageFont, ImageChops
from lena_config import ROOT


def fading_checker(width, height, dark):
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    cell = max(5, round(height / 5))
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, x + cell - 1, y + cell - 1),
                    fill=("#32373D" if dark else "#D9D7DD"),
                )
    horizontal = Image.new("L", (width, 1))
    horizontal.putdata(
        [
            round(
                190
                * min(
                    1, x / max(1, width * 0.23), (width - 1 - x) / max(1, width * 0.23)
                )
            )
            for x in range(width)
        ]
    )
    vertical = Image.new("L", (1, height))
    vertical.putdata(
        [
            round(
                255
                * min(
                    1,
                    (y + 1) / max(1, height * 0.2),
                    (height - y) / max(1, height * 0.2),
                )
            )
            for y in range(height)
        ]
    )
    alpha = ImageChops.multiply(
        horizontal.resize((width, height)), vertical.resize((width, height))
    )
    image.putalpha(ImageChops.multiply(image.getchannel("A"), alpha))
    return image


def action_pill(width, height, label, font_pixels, gradient=False, thunder=False):
    # 5x supersampling keeps capsule borders/text clean even on Windows DPI scaling.
    scale = 5
    w, h = width * scale, height * scale
    image = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(image)
    if gradient:
        stops = [(225, 193, 128), (194, 102, 169), (63, 37, 102)]
        for x in range(w):
            amount = x / max(1, w - 1) * 2
            i = min(1, int(amount))
            t = amount - i
            draw.line(
                (x, 0, x, h),
                fill=tuple(
                    round(a + (b - a) * t) for a, b in zip(stops[i], stops[i + 1])
                ),
            )
    else:
        draw.rectangle((0, 0, w, h), fill="#C26AAA")
    mask = Image.new("L", (w, h))
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, w - 2, h - 2), radius=h / 2, fill=255)
    image.putalpha(mask)
    draw.rounded_rectangle(
        (1, 1, w - 2, h - 2),
        radius=h / 2,
        outline="#F7F0F5",
        width=max(2, round(scale)),
    )
    font_file = ROOT / "assets/fonts/ZalandoSansExpanded-SemiBold.ttf"
    font_size = max(10, round(font_pixels * scale))
    gap = round(5 * scale)
    icon_size = round(h * 0.48) if thunder else 0
    while True:
        font = ImageFont.truetype(str(font_file), font_size)
        box = draw.textbbox((0, 0), label, font=font)
        tw = box[2] - box[0]
        total = tw + (icon_size + gap if thunder else 0)
        if total < w - h * 0.35 or font_size <= 10 * scale:
            break
        font_size -= 1
    x = (w - total) / 2
    if thunder:
        icon = (
            Image.open(ROOT / "assets/icons/quick-light.png")
            .convert("RGBA")
            .resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        )
        image.alpha_composite(icon, (round(x), round((h - icon_size) / 2)))
        # Keep the lightning icon in place, but pull the label 3 px left.
        # This gives "Quick Remove" a more balanced right-side breathing room.
        x += icon_size + gap - round(3 * scale)
    draw.text(
        (x - box[0], (h - (box[3] - box[1])) / 2 - box[1]),
        label,
        font=font,
        fill="#100D13",
    )
    return image.resize((width, height), Image.Resampling.LANCZOS)


def quick_outline_pill(width, height, label, font_pixels, dark=True):
    """Secondary Quick Remove action: transparent purple outline, theme-aware."""
    scale = 5
    w, h = width * scale, height * scale
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    purple = "#D579BC" if dark else "#8E3F86"
    radius = h / 2
    draw.rounded_rectangle(
        (
            round(scale * 0.8),
            round(scale * 0.8),
            w - round(scale * 0.8) - 1,
            h - round(scale * 0.8) - 1,
        ),
        radius=radius,
        outline=purple,
        width=max(2, round(1.5 * scale)),
    )
    font_file = ROOT / "assets/fonts/ZalandoSansExpanded-SemiBold.ttf"
    font_size = max(10, round(font_pixels * scale))
    gap = round(5 * scale)
    icon_size = round(h * 0.48)
    while True:
        font = ImageFont.truetype(str(font_file), font_size)
        box = draw.textbbox((0, 0), label, font=font)
        tw = box[2] - box[0]
        total = tw + icon_size + gap
        if total < w - h * 0.28 or font_size <= 10 * scale:
            break
        font_size -= 1
    x = (w - total) / 2
    icon = (
        Image.open(ROOT / "assets/icons/quick-light.png")
        .convert("RGBA")
        .resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    )
    tint = Image.new("RGBA", icon.size, purple)
    tint.putalpha(icon.getchannel("A"))
    image.alpha_composite(tint, (round(x), round((h - icon_size) / 2)))
    x += icon_size + gap - round(2 * scale)
    draw.text(
        (x - box[0], (h - (box[3] - box[1])) / 2 - box[1]),
        label,
        font=font,
        fill=purple,
    )
    return image.resize((width, height), Image.Resampling.LANCZOS)
