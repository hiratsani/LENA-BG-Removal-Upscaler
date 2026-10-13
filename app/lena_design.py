"""Hiratsani's 443px sidebar artboard, scaled as one layout."""

import tkinter as tk
import os, time, webbrowser
from functools import lru_cache
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance
from lena_config import ROOT
from lena_models import QUALITIES, REFINER, MODELS, path
from lena_motion import SmoothSidebarButton, motion_enabled
from lena_art import action_pill, fading_checker


class ModeSwitch(tk.Canvas):
    def __init__(self, parent, background, scale, command, up=False):
        super().__init__(
            parent,
            width=round(110.1 * scale),
            height=round(37.6 * scale),
            bd=0,
            highlightthickness=0,
            takefocus=True,
            cursor="hand2",
        )
        self.s = scale
        self.command = command
        self.position = float(up)
        self.job = None
        self.locked = False
        self.bg = ImageTk.PhotoImage(background)
        self.create_image(0, 0, image=self.bg, anchor="nw")
        self.rail = ImageTk.PhotoImage(
            Image.open(ROOT / "assets/custom/toggle-rail.png").resize(
                (round(110.1 * scale), round(37.6 * scale)), Image.Resampling.LANCZOS
            )
        )
        self.create_image(0, 0, image=self.rail, anchor="nw")
        self.knob = None
        self.knob_image = None
        self.paint()
        self.bind("<Button-1>", self.activate)
        self.bind("<space>", self.activate)
        self.bind("<Return>", self.activate)

    def activate(self, event=None):
        if not self.locked:
            self.command()
        return "break"

    def paint(self):
        x = (22 + 67.2 * self.position) * self.s
        y = 18.9 * self.s
        r = 9.6 * self.s
        shade = round(47 + (246 - 47) * max(0, min(1, self.position)))

        # Tk Canvas ovals are binary-edged and visibly stair-step at this size.
        # Render the knob supersampled with Pillow, then downsample with LANCZOS.
        diameter = max(2, round(r * 2))
        ss = 5
        knob = Image.new("RGBA", (diameter * ss, diameter * ss), (0, 0, 0, 0))
        ImageDraw.Draw(knob).ellipse(
            (0, 0, diameter * ss - 1, diameter * ss - 1),
            fill=(shade, shade, shade, 255),
        )
        knob = knob.resize((diameter, diameter), Image.Resampling.LANCZOS)
        self.knob_image = ImageTk.PhotoImage(knob)

        if self.knob is None:
            self.knob = self.create_image(
                round(x), round(y), image=self.knob_image, anchor="center"
            )
        else:
            self.coords(self.knob, round(x), round(y))
            self.itemconfigure(self.knob, image=self.knob_image)

    def set(self, up, animate=True):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        target = float(up)
        start = self.position
        began = time.monotonic()

        def tick():
            t = (
                min(1, (time.monotonic() - began) / 0.38)
                if animate and motion_enabled()
                else 1
            )
            self.position = start + (target - start) * (
                1 + 1.7 * (t - 1) ** 3 + 0.7 * (t - 1) ** 2
            )
            self.paint()
            self.job = self.after(16, tick) if t < 1 else None

        tick()

    def set_background(self, color):
        self.bg = ImageTk.PhotoImage(
            Image.new("RGB", (round(110.1 * self.s), round(37.6 * self.s)), color)
        )
        self.itemconfigure(1, image=self.bg)

    def destroy(self):
        if self.job:
            self.after_cancel(self.job)
        super().destroy()


@lru_cache(maxsize=8)
def transfer_art(task, language, dark):
    name = "transfer-remove" if task == "upscale" else "transfer-up"
    image = Image.open(
        ROOT / f'assets/custom/{name}-{"dark" if dark else "light"}.png'
    ).convert("RGBA")
    label = (
        ("Lanjut Hapus Background" if language == "id" else "Send to Remove BG")
        if task == "upscale"
        else ("Lanjut Upscale" if language == "id" else "Send to Upscale")
    )
    k = image.height / 60.5
    # Separate the supplied icon from its outline, then center text + gap + icon.
    bounds = (274, 17, 304, 45) if task == "upscale" else (161, 15, 190, 44)
    bounds = tuple(round(v * k) for v in bounds)
    icon = image.crop(bounds)
    icon = icon.crop(icon.getbbox())
    draw = ImageDraw.Draw(image)
    fs = max(8, round(15.5 * k))
    font_path = ROOT / "assets/fonts/ZalandoSansExpanded-SemiBold.ttf"
    font = ImageFont.truetype(str(font_path), fs)
    box = draw.textbbox((0, 0), label, font=font)
    tw = box[2] - box[0]
    gap = draw.textlength("  ", font=font)
    total = tw + gap + icon.width
    # Keep type and icon sizes stable; fit the capsule to each translation.
    inset = 9 * k
    padding = 18 * k
    image = Image.new("RGBA", (round(total + 2 * (inset + padding)), image.height))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (inset, 10 * k, image.width - inset, 52.3 * k),
        radius=21.15 * k,
        outline="#FFFFFF" if dark else "#171920",
        width=round(2 * k),
    )
    x = (image.width - total) / 2
    # The supplied typeface reads slightly high when mathematically centered.
    # Move the complete content group down together so text and icon stay aligned.
    content_y_offset = round(1.25 * k)
    y = round((image.height - (box[3] - box[1])) / 2 - box[1]) + content_y_offset
    draw.text(
        (round(x - box[0]), y), label, font=font, fill="#FFFFFF" if dark else "#171920"
    )
    image.alpha_composite(
        icon,
        (
            round(x + tw + gap),
            round((image.height - icon.height) / 2) + content_y_offset,
        ),
    )
    return image


class DesignSidebar:
    def draw_sidebar(self):
        if getattr(self, "_suspend_sidebar_draw", False):
            return
        c = self.side
        w = c.winfo_width()
        h_now = c.winfo_height()
        if w < 80 or h_now < 240:
            if not getattr(self, "_design_retry_job", None):

                def retry():
                    self._design_retry_job = None
                    self._design_layout = None
                    self.draw_sidebar()

                self._design_retry_job = self.after(30, retry)
            return
        # update_idletasks() inside the layout can deliver Configure recursively.
        # Never allow two construction passes to interleave on the same Canvas.
        if getattr(self, "_design_drawing", False):
            self._design_redraw_pending = True
            return
        self._design_drawing = True
        self._design_redraw_pending = False

        def release_draw_guard():
            self._design_drawing = False
            if self._design_redraw_pending:
                self._design_redraw_pending = False
                self._design_layout = None
                self.draw_sidebar()

        self.after(8, release_draw_guard)
        # Language is intentionally excluded: it only changes strings, never
        # geometry, colors, or images, so it never needs a full rebuild here.
        # change_language() updates the sidebar's text in place instead
        # (see retranslate_sidebar()); a stray draw_sidebar() call after a
        # language switch (e.g. from update_controls()) must stay a no-op.
        layout = (w, c.winfo_height(), self.dark)
        if getattr(self, "_design_layout", None) != layout:
            self._design_layout = layout
            self._shown_task = self.task
            if getattr(self, "_content_job", None):
                self.after_cancel(self._content_job)
                self._content_job = None
            for widget in getattr(self, "side_widgets", []):
                widget.destroy()
            c.delete("all")
            self.side_widgets = []
            self.side_images = []
            self.design_buttons = {}
            self.design_text = {}
            self._art_state = None
            h = c.winfo_height()
            s = min(w / 443, h / 960)
            self._design_s = s
            self._design_x = (w - 443 * s) / 2
            c.configure(scrollregion=(0, 0, w, h))
            top = (57, 43, 55) if self.dark else (244, 227, 234)
            end = (18, 19, 22) if self.dark else (245, 245, 247)
            right = (42, 40, 57) if self.dark else (229, 225, 241)
            # Precompute per-row colors in Python, then write the whole column in
            # one putdata() call instead of h*2 putpixel() calls. Same math
            # (including the max(1,...) divisor guard), same output.
            t0, t1, t2 = top
            r0, r1, r2 = right
            dt0, dt1, dt2 = end[0] - t0, end[1] - t1, end[2] - t2
            dr0, dr1, dr2 = end[0] - r0, end[1] - r1, end[2] - r2
            inv = 1.0 / max(1, 650 * s)
            data = [None] * (2 * h)
            for y in range(h):
                v = y * inv
                if v > 1:
                    v = 1
                data[y * 2] = (
                    round(t0 + dt0 * v),
                    round(t1 + dt1 * v),
                    round(t2 + dt2 * v),
                )
                data[y * 2 + 1] = (
                    round(r0 + dr0 * v),
                    round(r1 + dr1 * v),
                    round(r2 + dr2 * v),
                )
            bg = Image.new("RGB", (2, h))
            bg.putdata(data)
            bg = bg.resize((w, h), Image.Resampling.BILINEAR)
            self.side_images.append(ImageTk.PhotoImage(bg))
            c.create_image(0, 0, image=self.side_images[-1], anchor="nw")
            fg = "#F4F0F6" if self.dark else "#24212B"
            muted = "#A6A0AD" if self.dark else "#504A55"
            line = "#3B3540" if self.dark else "#CEC6D0"

            def text(
                key,
                x,
                y,
                label,
                fs=20,
                color=fg,
                font="Red Hat Display",
                group="common",
                anchor="nw",
                width=0,
            ):
                item = c.create_text(
                    x * s,
                    y * s,
                    text=label,
                    fill=color,
                    font=(font, -max(10, round(fs * s))),
                    anchor=anchor,
                    width=width * s,
                    tags=(group,),
                )
                self.design_text[key] = item
                return item

            decorations = []

            def picture(image, x, y, group="common"):
                self.side_images.append(ImageTk.PhotoImage(image))
                item = c.create_image(
                    x * s, y * s, image=self.side_images[-1], anchor="nw", tags=(group,)
                )
                decorations.append((item, image))
                return item

            def backdrop(button, width, height):
                xy = c.coords(button._side_window)
                x, y = map(round, xy or (0, 0))
                patch = bg.crop((x, y, x + width, y + height)).convert("RGBA")
                for item, decoration in decorations:
                    if c.itemcget(item, "state") == "hidden":
                        continue
                    dx, dy = map(round, c.coords(item))
                    if (
                        dx < x + width
                        and dy < y + height
                        and dx + decoration.width > x
                        and dy + decoration.height > y
                    ):
                        patch.alpha_composite(
                            decoration.convert("RGBA"), (dx - x, dy - y)
                        )
                return patch

            def control(
                key,
                x,
                y,
                width,
                height,
                label,
                command,
                fill="#605F65",
                fs=22,
                group="common",
                card=False,
                icon=None,
                art=None,
            ):
                f = s / self.sidebar._get_widget_scaling()
                button = SmoothSidebarButton(
                    c,
                    text=label,
                    command=command,
                    width=width * f,
                    height=height * f,
                    corner_radius=(16 if card else height / 2) * f,
                    font=("Red Hat Display Medium", max(10, round(fs * f))),
                    fg_color=fill,
                    bg_color=fill,
                    text_color="#F5F1F6",
                    hover_color="#757179",
                    compound="top" if icon else "left",
                )
                if icon:
                    button.configure(
                        image=ctk.CTkImage(
                            Image.open(
                                ROOT
                                / f'assets/icons/{icon}-{"dark" if self.dark else "light"}.png'
                            ),
                            size=(36 * f, 36 * f),
                        )
                    )
                if card:
                    button.configure(
                        text_color=fg, hover_color="#45404E" if self.dark else "#CAC2D0"
                    )
                if art:
                    button.configure(
                        text="",
                        border_spacing=0,
                        image=ctk.CTkImage(art, size=(width * f, height * f)),
                    )
                    button.art_only_hover = True
                button._side_window = c.create_window(
                    x * s,
                    y * s,
                    window=button,
                    anchor="nw",
                    width=width * s,
                    height=height * s,
                    tags=(group,),
                )
                # Composite smooth edges over the sidebar without a binary clip.
                button.backdrop = backdrop
                button.after_idle(button._draw)
                self.side_widgets.append(button)
                self.design_buttons[key] = button
                return button

            picture(
                Image.open(
                    ROOT / f'assets/icons/logo-{"dark" if self.dark else "light"}.png'
                ).resize((round(95 * s), round(95 * s)), Image.Resampling.LANCZOS),
                52,
                31,
            )
            text("brand", 169, 41, "LENA", 43, font="Zalando Sans Expanded SemiBold")
            text("author", 170, 94, "by Hiratsani", 20, color=muted)
            text("tagline", 52, 145, "", 20, width=345)
            photo_fill = "#D7D5D6" if self.dark else "#45414B"
            # Match the category cards below: photo starts at x=52 and clear
            # ends at x=394, with a 13px gap between the two buttons.
            photo = control(
                "photo",
                52,
                292,
                270,
                59,
                self.t("photo"),
                self.choose_photo,
                photo_fill,
            )
            photo.configure(
                text_color="#101218" if self.dark else "#F5F1F6",
                hover_color="#EAE7E9" if self.dark else "#625C69",
            )
            control("clear", 335, 292, 59, 59, "×", self.clear, "#68656C", 29)
            c.create_line(52 * s, 409 * s, 390 * s, 409 * s, fill=line)
            text(
                "mode_title",
                52,
                438,
                "Pilih Kualitas" if self.lang == "id" else "Choose Quality",
                26,
                font="Red Hat Display SemiBold",
                group="remove",
            )
            for i, (model, label) in enumerate(QUALITIES):
                b = control(
                    model,
                    52 + i * 116,
                    484,
                    108,
                    108,
                    label,
                    lambda m=model: self.pick_quality(m),
                    card=True,
                    icon=label.lower(),
                    fs=21,
                    group="remove",
                )
                f = s / self.sidebar._get_widget_scaling()
                b.configure(corner_radius=9 * f)
                b._quality_icon = b.cget("image")
                if label == "Better":
                    b._quality_icon.configure(size=(64 * f, 36 * f))
                b._empty_icon = ctk.CTkImage(
                    Image.new("RGBA", (36, 36)), size=(36 * f, 36 * f)
                )
                if model != "isnet-general":
                    b = control(
                        "download_" + model,
                        89 + i * 116,
                        508,
                        34,
                        34,
                        "↓",
                        lambda m=model: self.download_models([m]),
                        "#173D2A",
                        22,
                        group="remove",
                    )
                    b.configure(
                        text_color="#BDF5D2",
                        border_width=1,
                        border_color="#48C97B",
                        hover_color="#245A3C",
                    )
                    b.backdrop = lambda button, width, height, m=model: Image.new(
                        "RGBA", (width, height), self.design_buttons[m].cget("fg_color")
                    )
            # Hair & Fur lives in one subtle container, matching the supplied
            # reference: same left/right edge as the quality row, 16px inner
            # padding, copy on the left, action on the right.
            hair_panel_w = 340
            hair_panel_h = 67
            hair_panel = Image.new(
                "RGBA", (round(hair_panel_w * s), round(hair_panel_h * s)), (0, 0, 0, 0)
            )
            hair_panel_draw = ImageDraw.Draw(hair_panel)
            hair_panel_draw.rounded_rectangle(
                (0, 0, hair_panel.width - 1, hair_panel.height - 1),
                radius=max(1, round(8 * s)),
                fill=(255, 255, 255, 10) if self.dark else (0, 0, 0, 9),
            )
            hair_panel_item = picture(hair_panel, 52, 616, "remove")

            # Download and installed-model toggle intentionally occupy the exact
            # same slot so the layout never shifts when the model is installed.
            control(
                "hair_toggle",
                292,
                638,
                84,
                30,
                "OFF  ○",
                self.toggle_hair,
                "#2D2934",
                15,
                group="remove",
            )
            hair_dl = control(
                "download_hair",
                292,
                638,
                84,
                30,
                "↓",
                lambda: self.download_models([REFINER]),
                "#173D2A",
                20,
                group="remove",
            )
            hair_dl.configure(
                text_color="#BDF5D2",
                border_width=1,
                border_color="#48C97B",
                hover_color="#245A3C",
            )

            hair_label = text(
                "hair_label",
                68,
                633,
                "Rambut & bulu?" if self.lang == "id" else "Hair & fur?",
                20,
                font="Red Hat Display SemiBold",
                group="remove",
            )
            # Keep the info icon a fixed visual gap after the translated label.
            hair_label_box = c.bbox(hair_label)
            info_x = (
                ((hair_label_box[2] + round(8 * s)) / s)
                if hair_label_box
                else (216 if self.lang == "id" else 175)
            )
            info = text(
                "hair_info", info_x, 631, "ⓘ", 20, color="#78B7E8", group="remove"
            )
            # Keep the helper copy on one line in every state/language, exactly
            # like the reference card. It must never wrap below the container.
            text(
                "hair_hint",
                68,
                659,
                (
                    "Aktifkan hanya jika terlihat."
                    if self.lang == "id"
                    else "Only turn on if hair or fur is visible."
                ),
                14,
                width=0,
                group="remove",
            )

            def hide_tip(event=None):
                tip = getattr(self, "_hair_tip", None)
                if tip is not None:
                    tip.destroy()
                    self._hair_tip = None

            def show_tip(event=None):
                hide_tip()
                tip = tk.Toplevel(self)
                self._hair_tip = tip
                tip.overrideredirect(True)
                tip_text = (
                    "Aktifkan hanya untuk rambut, bulu hewan, bulu burung, atau objek berbulu halus."
                    if self.lang == "id"
                    else "Only turn on for hair, furry animals, feathers, or fuzzy objects."
                )
                tk.Label(
                    tip,
                    text=tip_text,
                    wraplength=260,
                    padx=12,
                    pady=9,
                    bg="#282B31",
                    fg="#F4F0F6",
                ).pack()
                tip.geometry(
                    f"+{c.winfo_rootx()+round(52*s)}+{c.winfo_rooty()+round(c.coords(info)[1]+28*s)}"
                )

            c.tag_bind(info, "<Enter>", show_tip)
            c.tag_bind(info, "<Leave>", hide_tip)
            text(
                "description",
                52,
                708,
                MODELS[self.selected][1 if self.lang == "id" else 2],
                20,
                color=muted,
                width=342,
                group="remove",
            )
            c.create_line(
                52 * s, 790 * s, 391 * s, 790 * s, fill=line, tags=("remove",)
            )
            for x, y, width, height, group in [
                (35, 822, 373, 66, "remove"),
                (58, 609, 326, 59, "upscale"),
            ]:
                picture(
                    fading_checker(round(width * s), round(height * s), self.dark),
                    x,
                    y,
                    group,
                )
            control(
                "start",
                92,
                822,
                260,
                66,
                "",
                self.start,
                "#392647",
                group="remove",
                art=action_pill(round(260 * s), round(66 * s), "start", 40 * s, True),
            )
            for i, n in enumerate((2, 4)):
                b = control(
                    f"scale{n}",
                    52 + i * 109,
                    467,
                    95,
                    95,
                    f"{n}x",
                    lambda n=n: self.set_scale(n),
                    card=True,
                    fs=29,
                    group="upscale",
                )
                b.configure(
                    font=(
                        "Zalando Sans Expanded SemiBold",
                        max(12, round(28 * s / self.sidebar._get_widget_scaling())),
                    )
                )
                b.centered_glyph = True
            text("input_size", 330, 483, "—", 19, anchor="center", group="upscale")
            text("arrow", 330, 518, "↓", 32, anchor="center", group="upscale")
            text(
                "output_size",
                330,
                554,
                "—",
                20,
                font="Red Hat Display SemiBold",
                anchor="center",
                group="upscale",
            )
            control(
                "upscale",
                127,
                609,
                188,
                59,
                "",
                self.start,
                "#392647",
                group="upscale",
                art=action_pill(round(188 * s), round(59 * s), "upscale", 34 * s, True),
            )
            thunder = Image.open(ROOT / "assets/icons/quick-dark.png").convert("RGBA")
            thunder.thumbnail((round(20 * s), round(27 * s)))
            tint = Image.new("RGBA", thunder.size, "#C26AAA")
            tint.putalpha(thunder.getchannel("A"))
            picture(tint, 133, 691, "upscale")
            text(
                "up_hint",
                154,
                686,
                self.t("upscale_hint"),
                16,
                color=muted,
                width=215,
                group="upscale",
            )
            text(
                "copyright",
                221.5,
                h / s - 52,
                "Copyright © 2026 – Hiratsani",
                13,
                color=muted,
                anchor="center",
            )
            link = text(
                "instagram",
                221.5,
                h / s - 30,
                "Help? Instagram: Hiratsani",
                13,
                color=muted,
                anchor="center",
            )

            def open_instagram(event=None):
                url = "https://www.instagram.com/hiratsani/"
                if os.name == "nt":
                    try:
                        os.startfile(url)
                        return
                    except OSError:
                        pass
                webbrowser.open(url)

            c.tag_bind(link, "<Button-1>", open_instagram)
            c.tag_bind(
                link,
                "<Enter>",
                lambda e: (c.configure(cursor="hand2"), c.itemconfigure(link, fill=fg)),
            )
            c.tag_bind(
                link,
                "<Leave>",
                lambda e: (c.configure(cursor=""), c.itemconfigure(link, fill=muted)),
            )
            knots = [
                (0, 0),
                (170, 170),
                (292, 225),
                (409, 315),
                (484, 385),
                (625, 510),
                (700, 581),
                (757, 631),
                (790, 659),
                (822, 684),
                (935, 777),
                (1006, 841),
                (1100, 960),
            ]

            def compact(y):
                for (a, b), (d, e) in zip(knots, knots[1:]):
                    if y <= d:
                        return (b + (y - a) / (d - a) * (e - b)) * min(1, h / (960 * s))
                return y

            for item in c.find_all():
                if item in (
                    c.find_all()[0],
                    self.design_text["copyright"],
                    self.design_text["instagram"],
                ):
                    continue
                coords = c.coords(item)
                c.coords(
                    item,
                    [
                        compact(v / s) * s if i % 2 else v + self._design_x
                        for i, v in enumerate(coords)
                    ],
                )
            # FIX 2: stack the mode-section rows with one consistent gap, then
            # center the whole stack between the two divider lines. Bounds are
            # measured AFTER the text is filled (including the wrapped category
            # note), so the rhythm matches the reference layout in every
            # language/theme; nothing here guesses y positions.
            c.update_idletasks()
            top_line = compact(409) * s
            bottom_line = compact(790) * s
            rows = [
                [self.design_text["mode_title"]],
                [self.design_buttons[k]._side_window for k, _ in QUALITIES]
                + [
                    self.design_buttons["download_" + k]._side_window
                    for k, _ in QUALITIES
                    if k != "isnet-general"
                ],
                [
                    hair_panel_item,
                    self.design_buttons["hair_toggle"]._side_window,
                    self.design_buttons["download_hair"]._side_window,
                    self.design_text["hair_label"],
                    self.design_text["hair_info"],
                    self.design_text["hair_hint"],
                ],
                [self.design_text["description"]],
            ]
            boxes = []
            for index, row in enumerate(rows):
                # The Hair & Fur card itself defines this row's visual bounds.
                # Text/button ink must not alter the spacing above or below it.
                if index == 2:
                    bb = [c.bbox(hair_panel_item)]
                else:
                    bb = [c.bbox(i) for i in row if c.bbox(i)]
                boxes.append((min(b[1] for b in bb), max(b[3] for b in bb)))
            heights = [bottom - top for top, bottom in boxes]
            available = bottom_line - top_line
            total = sum(heights)
            # Match the reference rhythm exactly: the quality row -> Hair & Fur
            # card gap and Hair & Fur card -> description gap are identical.
            gap = 24 * s
            outer = max(8 * s, (available - total - gap * (len(rows) - 1)) / 2)
            cursor = top_line + outer
            for row, (top, bottom) in zip(rows, boxes):
                delta = cursor - top
                if abs(delta) > 0.5:
                    for item in row:
                        c.move(item, 0, delta)
                cursor += (bottom - top) + gap

            # Micro-alignment inside the Hair & Fur card.  Center the two-line
            # copy as one optical block, and center the action pill by its actual
            # widget bounds.  This keeps both download and ON/OFF states in the
            # exact same vertical slot.
            panel_box = c.bbox(hair_panel_item)
            label_box = c.bbox(self.design_text["hair_label"])
            hint_box = c.bbox(self.design_text["hair_hint"])
            if panel_box and label_box and hint_box:
                panel_cy = (panel_box[1] + panel_box[3]) / 2
                copy_top = min(label_box[1], hint_box[1])
                copy_bottom = max(label_box[3], hint_box[3])
                copy_delta = panel_cy - (copy_top + copy_bottom) / 2
                if abs(copy_delta) > 0.25:
                    for item in (
                        self.design_text["hair_label"],
                        self.design_text["hair_info"],
                        self.design_text["hair_hint"],
                    ):
                        c.move(item, 0, copy_delta)

            action_box = c.bbox(self.design_buttons["hair_toggle"]._side_window)
            if panel_box and action_box:
                action_delta = (
                    (panel_box[1] + panel_box[3]) - (action_box[1] + action_box[3])
                ) / 2
                if abs(action_delta) > 0.25:
                    c.move(
                        self.design_buttons["hair_toggle"]._side_window, 0, action_delta
                    )
                    c.move(
                        self.design_buttons["download_hair"]._side_window,
                        0,
                        action_delta,
                    )
            # FIX 4: jangan trigger slide animation cuma karena sidebar
            # di-redraw (switch theme/language). Animasi cukup jalan saat
            # task beneran berubah, biar nggak ninggalin artefak garis.
            self._shown_task = self.task
            # Row alignment moves canvas windows without changing their size;
            # refresh the sampled backdrop at their final positions as well.
            for button in self.design_buttons.values():
                button._draw()
        self.refresh_sidebar_selection()

    def retranslate_sidebar(self):
        """Update every language-dependent label in place, with no destroy/rebuild.

        draw_sidebar() only rebuilds when (w,h,dark,lang) changes as a whole;
        without this, a language switch fell through to a full teardown and
        redraw of the entire sidebar (gradient repaint, every icon reloaded
        from disk, every button recreated), which is what made the language
        switch flash/glitch for about a second. Language is the one part of
        that tuple that never needs new geometry, colors, or images -- only
        different strings -- so it gets its own lightweight path.
        """
        if not getattr(self, "design_text", None):
            return
        c = self.side
        s = self._design_s
        id_ = self.lang == "id"
        self.design_buttons["photo"].configure(text=self.t("photo"))
        c.itemconfigure(
            self.design_text["mode_title"],
            text="Pilih Kualitas" if id_ else "Choose Quality",
        )
        c.itemconfigure(
            self.design_text["hair_label"],
            text="Rambut & bulu?" if id_ else "Hair & fur?",
        )
        c.itemconfigure(
            self.design_text["hair_hint"],
            text=(
                "Aktifkan hanya jika terlihat."
                if id_
                else "Only turn on if hair or fur is visible."
            ),
        )
        c.itemconfigure(self.design_text["up_hint"], text=self.t("upscale_hint"))
        # The info icon sits at a fixed gap after the label; the label's
        # rendered width changes with the language, so its position is
        # recomputed the same way draw_sidebar() first placed it.
        hair_label_box = c.bbox(self.design_text["hair_label"])
        info_x = (
            (hair_label_box[2] + round(8 * s))
            if hair_label_box
            else round((200 if id_ else 159) * s)
        )
        info_y = c.coords(self.design_text["hair_info"])[1]
        c.coords(self.design_text["hair_info"], info_x, info_y)
        self.refresh_sidebar_selection()

    def refresh_sidebar_selection(self):
        if not getattr(self, "design_buttons", None):
            return
        c = self.side
        s = self._design_s
        f = s / self.sidebar._get_widget_scaling()
        height = c.winfo_height()
        c.coords(
            self.design_text["copyright"], self._design_x + 221.5 * s, height - 52 * s
        )
        c.coords(
            self.design_text["instagram"], self._design_x + 221.5 * s, height - 30 * s
        )
        changed = self._shown_task != self.task
        for group in ("remove", "upscale"):
            c.itemconfigure(group, state="normal" if group == self.task else "hidden")
        c.itemconfigure(
            self.design_text["tagline"],
            text=(
                self.t("up_tagline")
                if self.task == "upscale"
                else self.t("remove_tagline")
            ),
        )
        if changed:
            if hasattr(self, "mode_switch"):
                self.mode_switch.set(self.task == "upscale", animate=True)
            self._shown_task = self.task
            self.animate_content(self.task)
        if hasattr(self, "mode_switch"):
            self.mode_switch.locked = self.busy
        for model, label in QUALITIES:
            b = self.design_buttons[model]
            ready = path(model) is not None
            selected = ready and model == self.selected
            purple = model == "mvanet"
            if self.dark:
                fill = (
                    ("#4C345F" if purple else "#254F78")
                    if selected
                    else (("#292332" if purple else "#202833") if ready else "#29292D")
                )
                border = ("#BD88DC" if purple else "#78B7E8") if selected else "#47434D"
            else:
                fill = (
                    ("#DDC2EC" if purple else "#BCDDF5")
                    if selected
                    else (("#E9E3ED" if purple else "#E5EBF1") if ready else "#DEDDDF")
                )
                border = ("#9560B5" if purple else "#3E85B8") if selected else "#C9C3CD"
            b._normal_border = border
            b._normal_width = 1
            # A fast quality switch must never leave the previous card's hover/press
            # animation painting over its newly configured unselected color.
            if getattr(b, "_motion_job", None):
                try:
                    b.after_cancel(b._motion_job)
                except Exception:
                    pass
                b._motion_job = None
            b._motion_level = 0
            b.configure(
                fg_color=fill,
                bg_color=fill,
                border_width=1,
                border_color=border,
                state="normal" if ready and not self.busy else "disabled",
                text_color_disabled="#8A868F",
            )
            b._draw()
            desired_icon = b._quality_icon if ready else b._empty_icon
            if b.cget("image") is not desired_icon:
                b.configure(image=desired_icon)
            if model != "isnet-general":
                dl = self.design_buttons["download_" + model]
                c.itemconfigure(
                    dl._side_window,
                    state="normal" if self.task == "remove" and not ready else "hidden",
                )
                dl.configure(state="disabled" if self.busy else "normal")
        hair_ready = path(REFINER) is not None
        if not hair_ready:
            self.hair_fur = False
        toggle = self.design_buttons["hair_toggle"]
        c.itemconfigure(
            toggle._side_window,
            state="normal" if self.task == "remove" and hair_ready else "hidden",
        )
        toggle.configure(
            text="ON  ●" if self.hair_fur else "OFF  ○",
            fg_color=(
                ("#503459" if self.hair_fur else "#2D2934")
                if self.dark
                else ("#D8BFE6" if self.hair_fur else "#E6E0E9")
            ),
            border_width=1,
            border_color=(
                ("#B77BC6" if self.hair_fur else "#77717D")
                if self.dark
                else ("#9161A5" if self.hair_fur else "#A49BAA")
            ),
            text_color=(
                ("#F5F1F6" if self.hair_fur else "#B7B4BA") if self.dark else "#34263E"
            ),
            hover_color=(
                ("#654371" if self.hair_fur else "#3A3740") if self.dark else "#D1C3DA"
            ),
            state="disabled" if self.busy else "normal",
        )
        dl = self.design_buttons["download_hair"]
        c.itemconfigure(
            dl._side_window,
            state="normal" if self.task == "remove" and not hair_ready else "hidden",
        )
        dl.configure(state="disabled" if self.busy else "normal")
        c.itemconfigure(
            self.design_text["description"],
            text=MODELS[self.selected][1 if self.lang == "id" else 2],
        )
        missing = path(self.selected) is None
        self.design_buttons["start"].configure(
            state="disabled" if missing and not self.busy else "normal"
        )
        for n in (2, 4):
            b = self.design_buttons[f"scale{n}"]
            selected = n == self.scale
            fill = (
                ("#3A2E47" if selected else "#2D2B33")
                if self.dark
                else ("#DFCCE8" if selected else "#D8D2DC")
            )
            b._normal_border = "#AC78C5" if selected else fill
            b._normal_width = 1 if selected else 0
            control_state = "disabled" if self.busy else "normal"
            if (
                b.cget("fg_color") != fill
                or b.cget("border_width") != b._normal_width
                or b.cget("state") != control_state
            ):
                b.configure(
                    fg_color=fill,
                    bg_color=fill,
                    border_color=b._normal_border,
                    border_width=b._normal_width,
                    state=control_state,
                )
        c.itemconfigure(
            self.design_text["input_size"],
            text=f"{self.source.width} x {self.source.height}" if self.source else "—",
        )
        c.itemconfigure(
            self.design_text["output_size"],
            text=(
                f"{self.source.width*self.scale} x {self.source.height*self.scale}"
                if self.source
                else "—"
            ),
        )
        state = (self.busy, missing, self.lang)
        if state != self._art_state:
            self._art_state = state
            for key, width, height, label, fs in [
                (
                    "start",
                    260,
                    66,
                    (
                        self.t("cancel")
                        if self.busy
                        else ("Hapus Latar" if self.lang == "id" else "Remove BG")
                    ),
                    28,
                ),
                (
                    "upscale",
                    188,
                    59,
                    self.t("cancel") if self.busy else "Upscale",
                    27 if self.busy else 32,
                ),
            ]:
                b = self.design_buttons[key]
                if b._motion_job:
                    b.after_cancel(b._motion_job)
                    b._motion_job = None
                b._art_frames = None
                b._motion_level = 0
                art = action_pill(
                    round(width * s), round(height * s), label, fs * s, True
                )
                # A missing model must read as unavailable at a glance. Keep the
                # original geometry/checkerboard, but desaturate and dim only
                # the primary Remove BG artwork.
                if key == "start" and missing and not self.busy:
                    art = ImageEnhance.Color(art).enhance(0.0)
                    art = ImageEnhance.Brightness(art).enhance(0.48)
                b.configure(image=ctk.CTkImage(art, size=(width * f, height * f)))

    def animate_content(self, group):
        if not motion_enabled():
            return
        c = self.side
        if getattr(self, "_content_job", None):
            self.after_cancel(self._content_job)
            for item, coords in getattr(self, "_content_coords", {}).items():
                c.coords(item, *coords)
            for item, color in getattr(self, "_content_colors", {}).items():
                c.itemconfigure(item, fill=color)
        # FIX 5: cuma slide/fade teks. Image & line dekoratif dulu ikut
        # kegeser animasi dan bisa ninggalin artefak garis/checker setelah
        # theme switch, jadi sekarang mereka diem di tempatnya.
        items = [i for i in c.find_withtag(group) if c.type(i) == "text"]
        self._content_coords = {i: c.coords(i) for i in items}
        self._content_colors = {i: c.itemcget(i, "fill") for i in items}
        backdrop = "#6D6E75" if self.dark else "#D8CFD4"
        bg = c.winfo_rgb(backdrop)
        targets = {i: c.winfo_rgb(color) for i, color in self._content_colors.items()}
        started = time.monotonic()

        def tick():
            t = min(1, (time.monotonic() - started) / 0.20)
            eased = 1 - (1 - t) ** 3
            offset = 8 * self._design_s * (1 - eased)
            for item, coords in self._content_coords.items():
                c.coords(
                    item,
                    *[v + offset if i % 2 == 0 else v for i, v in enumerate(coords)],
                )
            for item, target in targets.items():
                shade = "#" + "".join(
                    f"{round((x+(y-x)*eased)/257):02x}" for x, y in zip(bg, target)
                )
                c.itemconfigure(item, fill=shade)
            self._content_job = self.after(16, tick) if t < 1 else None

        tick()
