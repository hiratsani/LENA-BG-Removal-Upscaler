"""Short event-driven transitions; no animation timer remains active at rest."""

import ctypes, os, time
import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageDraw, ImageTk, ImageFont


def motion_enabled():
    if os.name != "nt":
        return True
    enabled = ctypes.c_int(1)
    return bool(
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
        and enabled.value
    )


def fade_window(win):
    if not motion_enabled():
        return
    win.attributes("-alpha", 0)
    started = time.monotonic()

    def tick():
        if not win.winfo_exists():
            return
        amount = min(1, (time.monotonic() - started) / 0.22)
        win.attributes("-alpha", 1 - (1 - amount) ** 3)
        if amount < 1:
            win.after(16, tick)

    win.after(16, tick)


class MotionButton(ctk.CTkButton):
    def _create_grid(self):
        super()._create_grid()
        # Circular buttons need room for their glyph; CTk otherwise reserves
        # one full corner radius on both sides and collapses the label.
        padding = (
            0
            if self._image is not None and not self._text
            else self._apply_widget_scaling(
                min(self._corner_radius, self._desired_width * 0.18)
            )
        )
        if self._compound == "top":
            padding = self._apply_widget_scaling(3)
        self.grid_columnconfigure((0, 4), minsize=padding)

    def __init__(self, *args, **kwargs):
        self._motion_job = None
        self._art_frames = None
        self._motion_level = 0
        super().__init__(*args, **kwargs)
        self._canvas.configure(takefocus=True)
        self.bind("<FocusIn>", lambda e: self._focus(True), add="+")
        self.bind("<FocusOut>", lambda e: self._focus(False), add="+")
        self.bind("<Key-space>", lambda e: self.invoke(), add="+")
        self.bind("<Return>", lambda e: (self.invoke(), "break")[1], add="+")
        self.bind("<ButtonPress-1>", self._press, add="+")
        self._normal_border = self.cget("border_color")
        self._normal_width = self.cget("border_width")

    def _focus(self, on):
        on = on and getattr(self.winfo_toplevel(), "_keyboard_navigation", False)
        self.configure(
            border_width=max(2, self._normal_width) if on else self._normal_width,
            border_color="#78B7E8" if on else self._normal_border,
        )

    def transition_from(self, color, duration=0.22):
        target = self.cget("fg_color")
        a = self.winfo_rgb(color)
        b = self.winfo_rgb(target)
        started = time.monotonic()
        if not motion_enabled():
            return
        if self._motion_job:
            self.after_cancel(self._motion_job)
            self._motion_job = None

        def tick():
            if not self.winfo_exists():
                return
            t = min(1, (time.monotonic() - started) / duration)
            amount = 1 - (1 - t) ** 3
            shade = "#" + "".join(
                f"{round((x+(y-x)*amount)/257):02x}" for x, y in zip(a, b)
            )
            # Keep the configured selection color immutable, even when hover
            # interrupts this transition halfway through.
            self._paint_color(shade)
            self._motion_job = self.after(16, tick) if t < 1 else None

        tick()

    def _on_enter(self, event=None):
        self._mouse_inside = True
        if self.cget("state") == "disabled":
            return
        self.configure(cursor="hand2")
        self._animate(1)

    def _on_leave(self, event=None):
        self._mouse_inside = False
        self._click_animation_running = False
        self._animate(0)
        self._scale_release()

    def _press(self, event=None):
        self.winfo_toplevel()._keyboard_navigation = False
        self._focus(False)
        if self.cget("state") != "disabled":
            self._animate(0.15, duration=0.07)
            self._scale_press()

    def _on_release(self, event=None):
        # CTk 6 dispatches commands on release, gated by _mouse_inside.
        # Do not queue CTk's delayed callback: commands can destroy this button.
        self._scale_release()
        if not self._mouse_inside or self.cget("state") == "disabled":
            return
        self._animate(1, duration=0.18)
        self.invoke()

    def _scale_press(self):
        window = getattr(self, "_side_window", None)
        if window is None:
            return
        canvas = self.master
        try:
            info = canvas.coords(window)
        except Exception:
            return
        current = canvas.itemcget(window, "width"), canvas.itemcget(window, "height")
        if not current[0]:
            return
        if getattr(self, "_scale_origin", None) is not None or not motion_enabled():
            return
        w, h = float(current[0]), float(current[1])
        shrink = 0.025
        self._scale_origin = (info[0], info[1], w, h)
        canvas.coords(window, info[0] + w * shrink / 2, info[1] + h * shrink / 2)
        canvas.itemconfigure(window, width=w * (1 - shrink), height=h * (1 - shrink))

    def _scale_release(self):
        origin = getattr(self, "_scale_origin", None)
        window = getattr(self, "_side_window", None)
        if origin is None or window is None:
            return
        canvas = self.master
        x, y, w, h = origin
        self._scale_origin = None
        try:
            canvas.coords(window, x, y)
            canvas.itemconfigure(window, width=w, height=h)
        except Exception:
            pass

    def _paint_color(self, color):
        # Image-art buttons already contain their complete rounded silhouette.
        # Painting CTk's inner rectangle underneath the transparent corners is
        # what made hover spill a few pixels outside the pill.
        if getattr(self, "art_only_hover", False):
            return
        self._canvas.itemconfig("inner_parts", fill=color, outline=color)
        if self._text_label:
            self._text_label.configure(bg=color)
        if self._image_label:
            self._image_label.configure(bg=color)

    def _animate(self, target, duration=0.20):
        if self._motion_job:
            self.after_cancel(self._motion_job)
            self._motion_job = None
        start = self._motion_level
        started = time.monotonic()
        base = self._apply_appearance_mode(self.cget("fg_color"))
        hover = self._apply_appearance_mode(self.cget("hover_color"))
        if base == "transparent":
            base = self._apply_appearance_mode(self.cget("bg_color"))
        a = self.winfo_rgb(base)
        b = self.winfo_rgb(hover)
        art = self.cget("image")
        if (
            art
            and not self.cget("text")
            and art.cget("size")[0] > 80
            and self._art_frames is None
        ):
            original = art.cget("light_image") or art.cget("dark_image")
            self._art_frames = [
                ctk.CTkImage(
                    ImageEnhance.Brightness(original).enhance(
                        1 + i * getattr(self, "art_hover_brightness_step", 0.012)
                    ),
                    size=art.cget("size"),
                )
                for i in range(9)
            ]
        enabled = motion_enabled()

        def tick():
            if not self.winfo_exists():
                return
            t = min(1, (time.monotonic() - started) / duration) if enabled else 1
            level = start + (target - start) * (1 - (1 - t) ** 3)
            self._motion_level = level
            color = "#" + "".join(
                f"{round((x+(y-x)*level)/257):02x}" for x, y in zip(a, b)
            )
            # Draw directly so fg_color remains the stable baseline.
            self._paint_color(color)
            if self._art_frames:
                super(MotionButton, self).configure(
                    image=self._art_frames[round(level * 8)]
                )
            self._motion_job = self.after(16, tick) if t < 1 else None

        tick()

    def destroy(self):
        if self._motion_job:
            self.after_cancel(self._motion_job)
            self._motion_job = None
        super().destroy()


class SmoothSidebarButton(MotionButton):
    """Antialiased sidebar surfaces composited against the actual sidebar art."""

    backdrop = None

    def _create_grid(self):
        super()._create_grid()
        if self._image_label is not None and self._image is not None and not self._text:
            # Complete pill artwork must occupy the whole widget. CTk's normal
            # image padding and Tk Label border otherwise crop its curved ends.
            self._image_label.configure(
                borderwidth=0, highlightthickness=0, padx=0, pady=0
            )
            self._image_label.grid_remove()

    def _surface(self, color=None):
        w = max(
            1,
            self.winfo_width(),
            round(self._apply_widget_scaling(self._current_width)),
        )
        h = max(
            1,
            self.winfo_height(),
            round(self._apply_widget_scaling(self._current_height)),
        )
        image = self.backdrop(self, w, h)
        if isinstance(self._image, ctk.CTkImage) and not self._text:
            original = self._image.cget("light_image") or self._image.cget("dark_image")
            image.alpha_composite(
                original.convert("RGBA").resize((w, h), Image.Resampling.LANCZOS)
            )
            return image
        ss = 4
        layer = Image.new("RGBA", (w * ss, h * ss))
        draw = ImageDraw.Draw(layer)
        radius = self._apply_widget_scaling(self._corner_radius) * ss
        border = round(self._apply_widget_scaling(self._border_width) * ss)
        fill = color or self._apply_appearance_mode(self._fg_color)
        draw.rounded_rectangle(
            (0, 0, w * ss - 1, h * ss - 1),
            radius=radius,
            fill=fill,
            outline=self._apply_appearance_mode(self._border_color),
            width=border,
        )
        if getattr(self, "centered_glyph", False):
            from lena_config import ROOT

            font = ImageFont.truetype(
                str(ROOT / "assets/fonts/ZalandoSansExpanded-SemiBold.ttf"),
                max(1, round(self._font[1] * self._get_widget_scaling() * ss)),
            )
            box = draw.textbbox((0, 0), self._text, font=font)
            ink = (
                self._text_color_disabled
                if self._state == "disabled"
                else self._text_color
            )
            ink = tuple(
                round(v / 257) for v in self.winfo_rgb(self._apply_appearance_mode(ink))
            )
            draw.text(
                (
                    (w * ss - box[2] + box[0]) / 2 - box[0],
                    (h * ss - box[3] + box[1]) / 2 - box[1],
                ),
                self._text,
                font=font,
                fill=ink,
            )
        image.alpha_composite(layer.resize((w, h), Image.Resampling.LANCZOS))
        return image

    def _draw(self, *args, **kwargs):
        super()._draw(*args, **kwargs)
        if self.backdrop is None:
            return
        if getattr(self, "centered_glyph", False) and self._text_label is not None:
            self._text_label.grid_remove()
        self._smooth_photo = ImageTk.PhotoImage(self._surface())
        self._canvas.delete("smooth_surface")
        self._canvas.create_image(
            0, 0, anchor="nw", image=self._smooth_photo, tags="smooth_surface"
        )
        self._update_image()

    def _update_image(self):
        super()._update_image()
        if (
            self.backdrop is None
            or self._image_label is None
            or self._text
            or not isinstance(self._image, ctk.CTkImage)
        ):
            return
        # One canvas surface owns both art and backdrop. A separate Label can
        # leave a one-pixel strip of its solid background at fractional DPI.
        self._image_label.grid_remove()
        self._smooth_photo = ImageTk.PhotoImage(self._surface())
        self._canvas.itemconfigure("smooth_surface", image=self._smooth_photo)

    def _paint_color(self, color):
        super()._paint_color(color)
        if self.backdrop is None or getattr(self, "art_only_hover", False):
            return
        self._smooth_photo = ImageTk.PhotoImage(self._surface(color))
        self._canvas.itemconfigure("smooth_surface", image=self._smooth_photo)


class QualityCard(MotionButton):
    """One clickable surface with separate heading and secondary text."""

    def __init__(self, *args, heading, details, **kwargs):
        self.heading = heading
        self.details = details
        self._rich_ready = False
        super().__init__(*args, **kwargs)
        self._rich_ready = True
        self._draw()

    def _draw(self, *args, **kwargs):
        super()._draw(*args, **kwargs)
        if not self._rich_ready:
            return
        if self._text_label:
            self._text_label.grid_remove()
        self._canvas.delete("quality_text")
        scale = self._get_widget_scaling()
        color = self._apply_appearance_mode(self.cget("text_color"))
        self._canvas.create_text(
            14 * scale,
            10 * scale,
            anchor="nw",
            text=self.heading,
            fill=color,
            font=("Red Hat Display", -round(18 * scale), "bold"),
            tags="quality_text",
        )
        self._canvas.create_text(
            14 * scale,
            36 * scale,
            anchor="nw",
            text=self.details,
            fill=color,
            font=("Red Hat Display", -round(12 * scale)),
            width=round((self._current_width - 28) * scale),
            tags="quality_text",
        )
