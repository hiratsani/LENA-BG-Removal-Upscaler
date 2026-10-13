"""Cached comparison with incremental strip copying on a single drawing surface."""

import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from PIL import Image, ImageDraw, ImageTk
from lena_motion import MotionButton


class Preview(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bd=0, highlightthickness=0)
        self.source = self.result = None
        self.compare = True
        self.ratio = 0.5
        self.dark = True
        self.empty = ""
        self.hint = ""
        self.background_mode = "transparent"
        self._destroyed = False
        self.pending = None
        self.photos = []
        self.render_key = None
        self.render_count = 0
        self.iw = self.ih = 0
        self._renderer = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="lena-preview"
        )
        self._future = None
        self._future_key = None
        self._preview_cache = OrderedDict()
        self.zoom_enabled = False
        self.view_mode = "compare"
        self.zoom = None
        self.center = (0.5, 0.5)
        self.navigation_locked = False
        self.pan_start = None
        self.surface = tk.Canvas(self, bd=0, highlightthickness=0)
        self.display_photo = None
        self.edge = 0
        self.picture = self.surface.create_image(0, 0, anchor="nw")
        self.line = self.surface.create_line(0, 0, 0, 0, fill="white", width=2)
        self.handle = self.surface.create_oval(
            0, 0, 0, 0, fill="#FAF8FA", outline="#D0CDD2"
        )
        self.arrows = self.surface.create_text(
            0,
            0,
            text="\u2039  \u203a",
            fill="#303039",
            font=("Red Hat Display", 12, "bold"),
        )
        self.placeholder = tk.Label(
            self, text="", justify="center", font=("Red Hat Display", 12), bd=0
        )
        self.empty_title_text = "Start with a photo."
        self.empty_title = tk.Label(
            self, text="", font=("Red Hat Display", 24, "bold"), bd=0
        )
        self.empty_button = MotionButton(
            self,
            text="+ Choose Photo",
            command=self.choose_empty_photo,
            width=170,
            height=38,
            corner_radius=19,
            font=("Red Hat Display Medium", 14),
            fg_color="#9164B5",
            hover_color="#A578C7",
            text_color="#FFFFFF",
        )
        self.hint_label = tk.Label(self, font=("Red Hat Display", 10), bd=0)
        self.bind("<Configure>", self.schedule)
        self.surface.bind("<Button-1>", self.pointer_down)
        self.surface.bind("<B1-Motion>", self.pointer_move)

    def choose_empty_photo(self):
        app = self.winfo_toplevel()
        if not app.busy and getattr(app, "modal", None) is None:
            app.choose_photo()

    def set_images(self, source, result=None, reset=False):
        # Cached views must not retain full-resolution photos from old jobs.
        if source is not self.source or result is not self.result:
            self._preview_cache.clear()
        self.source, self.result = source, result
        if result is None:
            # Async preview preparation may take a frame; remove comparison
            # controls immediately when clearing or starting another run.
            for item in (self.line, self.handle, self.arrows):
                self.surface.itemconfigure(item, state="hidden")
        if source is None:
            self._preview_cache.clear()
        if reset:
            self.ratio = 0.5
            self.zoom = None
            self.center = (0.5, 0.5)
        self.schedule()

    def set_background(self, mode):
        if (
            mode not in ("transparent", "white", "black")
            or mode == self.background_mode
        ):
            return
        self.background_mode = mode
        self.render_key = None
        self._preview_cache.clear()
        self.schedule()

    def schedule(self, event=None):
        if self._destroyed:
            return
        if self.pending:
            self.after_cancel(self.pending)
        self.pending = self.after(40, self.render)

    def render(self):
        if self._destroyed:
            return
        # begin() can render immediately with a scheduled render still pending.
        # Cancel that timer first, so it cannot start a second polling chain.
        if self.pending:
            self.after_cancel(self.pending)
        self.pending = None
        w, h = max(1, self.winfo_width()), max(1, self.winfo_height())
        bg = "#1D1E23" if self.dark else "#FFFFFF"
        fg = "#A9A7B2" if self.dark else "#4F4A55"
        self.configure(bg=bg)
        for label in (self.placeholder, self.hint_label):
            label.configure(bg=bg, fg=fg)
        self.placeholder.configure(text=self.empty, wraplength=max(100, w - 50))
        self.empty_title.configure(
            text=self.empty_title_text,
            bg=bg,
            fg="#F5F3F8" if self.dark else "#24212B",
            wraplength=max(100, w - 40),
        )
        self.empty_button.configure(bg_color=bg)
        if self.source is None:
            self.surface.place_forget()
            self.hint_label.place_forget()
            # Measure wrapped text so both visible gaps stay equal in either
            # language and at every window size / display scale.
            title_h = self.empty_title.winfo_reqheight()
            body_h = self.placeholder.winfo_reqheight()
            button_h = round(self.empty_button._apply_widget_scaling(38))
            gap = round(18 * self.empty_button._get_widget_scaling())
            top = -(title_h + body_h + button_h + 2 * gap) / 2
            self.empty_title.place(relx=0.5, rely=0.5, y=round(top), anchor="n")
            self.placeholder.place(
                relx=0.5, rely=0.5, y=round(top + title_h + gap), anchor="n"
            )
            self.empty_button.place(
                relx=0.5,
                rely=0.5,
                y=(top + title_h + body_h + 2 * gap)
                / self.empty_button._get_widget_scaling(),
                anchor="n",
            )
            self.surface.itemconfigure(self.picture, image="")
            self.display_photo = None
            self.photos = []
            self.render_key = None
            return
        self.placeholder.place_forget()
        self.empty_title.place_forget()
        self.empty_button.place_forget()
        if self.zoom_enabled and self.view_mode == "zoom":
            self.render_zoom(w, h, bg)
            return
        scale = min(w / self.source.width, h / self.source.height)
        self.iw, self.ih = max(1, round(self.source.width * scale)), max(
            1, round(self.source.height * scale)
        )
        key = (
            id(self.source),
            id(self.result),
            self.iw,
            self.ih,
            self.dark,
            self.background_mode,
        )
        if self.render_key != key:
            photos = self.prepared_photos(key)
            if photos is None:
                return
            self.photos = photos
            self.display_photo = tk.PhotoImage(
                master=self, width=self.iw, height=self.ih
            )
            self.tk.call(str(self.display_photo), "copy", str(self.photos[-1]))
            self.surface.itemconfigure(self.picture, image=self.display_photo)
            self.edge = 0
            self.render_key = key
            self.render_count += 1
        self.surface.place(
            relx=0.5, rely=0.5, anchor="center", width=self.iw, height=self.ih
        )
        self.hint_label.configure(text=self.hint, wraplength=max(100, w - 30))
        self.hint_label.place_forget()
        self.reveal()

    @staticmethod
    def compose_preview(
        source, result, width, height, dark, background_mode="transparent"
    ):
        """Pillow work only; Tk remains exclusively on the UI thread."""
        if background_mode == "white":
            checker = Image.new("RGBA", (width, height), "#FFFFFF")
        elif background_mode == "black":
            checker = Image.new("RGBA", (width, height), "#000000")
        else:
            checker = Image.new(
                "RGBA", (width, height), "#56585E" if dark else "#FFFFFF"
            )
            draw = ImageDraw.Draw(checker)
            for y in range(0, height, 16):
                for x in range(0, width, 16):
                    if (x // 16 + y // 16) % 2:
                        draw.rectangle(
                            (x, y, x + 15, y + 15),
                            fill="#45474D" if dark else "#DFDEE2",
                        )
        frames = []
        for original in (source, result):
            if original is None:
                continue
            frame = checker.copy()
            frame.alpha_composite(
                original.resize((width, height), Image.Resampling.LANCZOS).convert(
                    "RGBA"
                )
            )
            frames.append(frame)
        return frames

    def prepared_photos(self, key):
        cached = self._preview_cache.get(key)
        if cached:
            self._preview_cache.move_to_end(key)
            return cached[2]
        if self._future is not None:
            if not self._future.done():
                self.pending = self.after(16, self.render)
                return None
            future = self._future
            old_key = self._future_key
            self._future = None
            frames = future.result()
            if old_key == key:
                photos = []
                try:
                    for frame in frames:
                        photos.append(ImageTk.PhotoImage(frame, master=self))
                finally:
                    # ImageTk has already copied the pixels into Tcl/Tk. Keeping the
                    # Pillow RGBA compositing frames alive only doubles preview RAM.
                    for frame in frames:
                        try:
                            frame.close()
                        except Exception:
                            pass
                # One active preview is enough. Previous sizes/backgrounds can be
                # rebuilt asynchronously and otherwise waste several full UI bitmaps.
                self._preview_cache.clear()
                self._preview_cache[key] = (self.source, self.result, photos)
                return photos
        self._future_key = key
        self._future = self._renderer.submit(
            self.compose_preview,
            self.source,
            self.result,
            self.iw,
            self.ih,
            self.dark,
            self.background_mode,
        )
        self.pending = self.after(16, self.render)
        return None

    def destroy(self):
        self._destroyed = True
        if self.pending:
            self.after_cancel(self.pending)
            self.pending = None
        self._renderer.shutdown(wait=False, cancel_futures=True)
        if self._future is not None:
            self._future.cancel()
            self._future = None
        # Release Tk images here, on the UI thread, before destroying the canvas.
        self.surface.itemconfigure(self.picture, image="")
        self._preview_cache.clear()
        self.photos = []
        self.display_photo = None
        super().destroy()

    def reveal(self):
        if (
            self.source is None
            or self.iw < 1
            or (self.zoom_enabled and self.view_mode == "zoom")
        ):
            return
        if self.render_key != (
            id(self.source),
            id(self.result),
            self.iw,
            self.ih,
            self.dark,
            self.background_mode,
        ):
            return
        comparing = self.result is not None and self.compare
        self.hint_label.configure(text=self.hint if comparing else "")
        edge = (
            round(self.iw * self.ratio)
            if comparing
            else (self.iw if self.result is None else 0)
        )
        # Copy only the changed strip from cached pixels. One Canvas paints the
        # image and divider together, avoiding trails from moving child windows.
        if edge != self.edge and self.display_photo is not None:
            lo, hi = sorted((edge, self.edge))
            photo = self.photos[0] if edge > self.edge else self.photos[-1]
            self.tk.call(
                str(self.display_photo),
                "copy",
                str(photo),
                "-from",
                lo,
                0,
                hi,
                self.ih,
                "-to",
                lo,
                0,
            )
            self.edge = edge
        for item in (self.line, self.handle, self.arrows):
            self.surface.itemconfigure(item, state="normal" if comparing else "hidden")
        self.surface.configure(cursor="sb_h_double_arrow" if comparing else "")
        if comparing:
            center = min(max(edge, 16), max(16, self.iw - 16))
            middle = self.ih / 2
            self.surface.coords(
                self.line, min(edge, self.iw - 1), 0, min(edge, self.iw - 1), self.ih
            )
            self.surface.coords(
                self.handle, center - 14, middle - 14, center + 14, middle + 14
            )
            self.surface.coords(self.arrows, center, middle)

    def drag(self, event):
        if self.result is None or not self.compare or self.navigation_locked:
            return
        self.ratio = min(
            1, max(0, (event.x_root - self.surface.winfo_rootx()) / max(1, self.iw))
        )
        self.reveal()

    def set_view(self, mode):
        if self.navigation_locked:
            return
        self.view_mode = mode
        self.compare = mode == "compare"
        self.zoom = None
        self.center = (0.5, 0.5)
        self.schedule()

    def fit(self):
        if self.navigation_locked:
            return
        self.zoom = None
        self.center = (0.5, 0.5)
        self.schedule()

    def actual_size(self):
        if self.navigation_locked:
            return
        self.view_mode = "zoom"
        self.compare = False
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        self.schedule()

    def wheel(self, event):
        if not self.zoom_enabled or self.navigation_locked or self.source is None:
            return "break"
        target = self.result if self.result is not None else self.source
        fit = min(
            max(1, self.winfo_width() - 32) / target.width,
            max(1, self.winfo_height() - 66) / target.height,
        )
        old = self.zoom or fit
        new = min(8, max(min(fit, 0.05), old * 1.2 ** (event.delta / 120)))
        # Zoom toward the pointer, preserving its image coordinate.
        px = event.x_root - self.winfo_rootx() - self.winfo_width() / 2
        py = event.y_root - self.winfo_rooty() - self.winfo_height() / 2
        self.center = (
            self.center[0] + px * (1 / old - 1 / new) / target.width,
            self.center[1] + py * (1 / old - 1 / new) / target.height,
        )
        self.zoom = new
        self.view_mode = "zoom"
        self.compare = False
        self.schedule()
        return "break"

    def pointer_down(self, event):
        if self.navigation_locked:
            return
        if self.zoom_enabled and self.view_mode == "zoom":
            self.pan_start = (event.x_root, event.y_root, self.center)
        else:
            self.drag(event)

    def pointer_move(self, event):
        if self.navigation_locked:
            return
        if self.zoom_enabled and self.view_mode == "zoom" and self.pan_start:
            target = self.result if self.result is not None else self.source
            if target is None:
                return
            x, y, center = self.pan_start
            zoom = self._effective_zoom
            self.center = (
                center[0] - (event.x_root - x) / zoom / target.width,
                center[1] - (event.y_root - y) / zoom / target.height,
            )
            self.schedule()
        else:
            self.drag(event)

    def render_zoom(self, w, h, bg):
        target = self.result if self.result is not None else self.source
        vw, vh = max(1, w - 32), max(1, h - 66)
        fit = min(vw / target.width, vh / target.height)
        z = self.zoom or fit
        self._effective_zoom = z
        self.iw = min(vw, max(1, round(target.width * z)))
        self.ih = min(vh, max(1, round(target.height * z)))
        cw, ch = self.iw / z, self.ih / z
        left = max(0, min(target.width - cw, self.center[0] * target.width - cw / 2))
        top = max(0, min(target.height - ch, self.center[1] * target.height - ch / 2))
        self.center = ((left + cw / 2) / target.width, (top + ch / 2) / target.height)
        key = (
            "zoom",
            id(target),
            self.iw,
            self.ih,
            z,
            left,
            top,
            self.dark,
            self.background_mode,
        )
        if self.render_key != key:
            # Only the visible region is sampled; no enormous zoomed bitmap.
            crop = target.transform(
                (self.iw, self.ih),
                Image.Transform.EXTENT,
                (left, top, left + cw, top + ch),
                Image.Resampling.BICUBIC,
            )
            if self.background_mode == "white":
                checker = Image.new("RGBA", crop.size, "#FFFFFF")
            elif self.background_mode == "black":
                checker = Image.new("RGBA", crop.size, "#000000")
            else:
                checker = Image.new(
                    "RGBA", crop.size, "#56585E" if self.dark else "#FFFFFF"
                )
                draw = ImageDraw.Draw(checker)
                for y in range(0, self.ih, 16):
                    for x in range(0, self.iw, 16):
                        if (x // 16 + y // 16) % 2:
                            draw.rectangle(
                                (x, y, x + 15, y + 15),
                                fill="#45474D" if self.dark else "#DFDEE2",
                            )
            checker.alpha_composite(crop)
            self.display_photo = ImageTk.PhotoImage(checker)
            self.photos = []
            self.surface.itemconfigure(self.picture, image=self.display_photo)
            self.render_key = key
            self.render_count += 1
        for item in (self.line, self.handle, self.arrows):
            self.surface.itemconfigure(item, state="hidden")
        self.surface.configure(cursor="fleur")
        self.surface.place(
            relx=0.5, rely=0.5, anchor="center", width=self.iw, height=self.ih
        )
        self.hint_label.configure(
            text=f"{z:.0%} · "
            + getattr(self, "zoom_help", "Scroll to zoom · Drag to pan")
        )
        self.hint_label.place_forget()
