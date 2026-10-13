"""LENA desktop app. Inference runs in a cancellable, isolated process."""

import sys

if __name__ == "__main__":
    from lena_diagnostics import install

    install(worker=("--serve" in sys.argv or "--worker" in sys.argv))
if __name__ == "__main__" and "--serve" in sys.argv:
    from lena_worker import serve

    serve()
    sys.exit(0)
if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--worker":
    from lena_worker import run_request

    sys.exit(run_request(sys.argv[2]))

import os, ctypes, time, threading, queue, webbrowser, gc
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD
import customtkinter as ctk
from PIL import Image, ImageTk, ImageOps, ImageGrab
from lena_config import ROOT, HOME, CACHE, read_settings, save_settings
from lena_models import MODELS, QUALITIES, REFINER, path, saved_quality
from lena_downloads import prepare, Cancelled
from lena_preview import Preview
from lena_text import COPY
from lena_drop import PhotoDrop
from lena_loading import LoadingLogo
from lena_motion import MotionButton, fade_window

from lena_platform import IS_MAC, open_local, register_fonts as _register_fonts

if os.name == "nt":
    # Give source launches their own Windows identity before Tk creates a HWND.
    # Otherwise Windows can temporarily group the window under python.exe and
    # show Python's default feather icon in the taskbar.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Hiratsani.LENA")
    except (AttributeError, OSError):
        pass


def register_fonts():
    _register_fonts(ROOT / "assets/fonts")


def _trim_process_memory():
    """Return freed Python/Pillow pages to Windows when practical.

    This never drops live source/result pixels; it only collects unreachable
    objects and asks Windows to trim pages that no longer need to stay resident.
    """
    gc.collect()
    if os.name != "nt":
        return
    try:
        kernel = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        psapi.EmptyWorkingSet.restype = ctypes.c_int
        psapi.EmptyWorkingSet(kernel.GetCurrentProcess())
    except (AttributeError, OSError):
        pass


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        from lena_diagnostics import install, record

        install()
        register_fonts()
        super().__init__()
        self._closing = False
        self._processing_stage = ""
        self._matting_warning = False
        self._result_warning = False
        self.bind(
            "<FocusIn>",
            lambda e: (
                record("focus_in", busy=getattr(self, "busy", False))
                if e.widget is self
                else None
            ),
            add="+",
        )
        self.bind(
            "<FocusOut>",
            lambda e: (
                record("focus_out", busy=getattr(self, "busy", False))
                if e.widget is self
                else None
            ),
            add="+",
        )
        # Never expose the partially constructed Tk/CTk hierarchy. Windows can
        # map the root while widgets are still being created, which makes the
        # first launch look like a stack of unfinished rectangles. Keep the
        # complete root transparent until EnhancedApp has finished its final
        # maximize/layout/sidebar pass, then reveal everything at once.
        self._startup_reveal_pending = True
        # Keep the root genuinely unmapped during construction. Making an
        # already-mapped window merely transparent still lets Windows create a
        # taskbar button, which can briefly appear/disappear before the real UI
        # is ready. Withdrawing here prevents that shell registration entirely
        # until the final reveal.
        try:
            self.withdraw()
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            self._startup_reveal_pending = False
        self._startup_target_zoomed = os.name == "nt"
        self.settings = read_settings()
        # Restore the last user-facing preferences defensively. Older builds
        # used both en/eng and id/ind at UI boundaries, while settings.json
        # stores the canonical en/id + dark/light values.
        saved_lang = str(self.settings.get("language", "id")).lower()
        self.lang = "en" if saved_lang in ("en", "eng") else "id"
        saved_theme = str(self.settings.get("theme", "dark")).lower()
        self.dark = False if saved_theme == "light" else True
        self.mode = self.settings.get("mode", "auto")
        if self.mode not in ("auto", "cpu"):
            self.mode = "auto"
        self.selected = saved_quality(self.settings)
        self.hair_fur = False
        self.source = self.result = None
        self.source_name = "photo"
        self.busy = False
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.devices = []
        self.popup = None
        self.modal = None
        self.status_text = ""
        self.started = 0
        self.download_active = False
        self.side_images = []
        self.title("LENA 1.0")
        if os.name == "nt":
            self.iconbitmap(str(ROOT / "assets/LENA.ico"))
            # iconphoto also sets Tk's default icon for any native window that
            # gets created after the root (including source/debug launches).
            self._window_icon = ImageTk.PhotoImage(
                Image.open(ROOT / "assets/LENA.ico").convert("RGBA")
            )
            self.iconphoto(True, self._window_icon)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1280,int(sw*.9))}x{min(820,int(sh*.85))}")
        self.minsize(760, 510)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=285, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.side = tk.Canvas(self.sidebar, highlightthickness=0, bd=0)
        self.side_scroll = ctk.CTkScrollbar(
            self.sidebar, width=7, command=self.side.yview
        )
        self.side_scroll.pack(side="right", fill="y")
        self.side.configure(yscrollcommand=self.side_scroll.set)
        self.side.pack(side="left", fill="both", expand=True)
        self.side.bind("<Configure>", lambda e: self.draw_sidebar())
        self.side.bind(
            "<MouseWheel>",
            lambda e: self.side.yview_scroll(-int(e.delta / 120) * 3, "units"),
        )
        self.main = ctk.CTkFrame(self, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.bind("<Configure>", self.responsive, add="+")
        self.toolbar = ctk.CTkFrame(self.main, height=50, corner_radius=0)
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_columnconfigure((0, 2), weight=1, uniform="header")
        self.controls = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.controls.grid(row=0, column=2, pady=10, padx=8, sticky="e")
        self.save_button = self.button(
            self.toolbar, "Save PNG", self.save, width=112, color="#117AD3"
        )
        self.save_button.grid(row=0, column=1, pady=10)
        self.settings_button = self.button(
            self.controls, "", self.open_settings, width=36
        )
        self.settings_button.pack(side="left", padx=(18, 3))
        self.guide_button = self.button(self.controls, "", self.open_guide, width=36)
        self.guide_button.pack(side="left", padx=3)
        self.workspace = ctk.CTkFrame(self.main, corner_radius=0)
        self.workspace.grid(row=1, column=0, sticky="nsew", padx=9, pady=(9, 0))
        self.info_bar = ctk.CTkFrame(self.workspace, corner_radius=0)
        self.info_bar.pack(fill="x", padx=12, pady=(10, 3))
        self.donation = self.button(
            self.info_bar, "buy me a coffee :D", self.donate, width=154, color="#25262A"
        )
        self.donation.pack(side="right")
        self.status_label = ctk.CTkLabel(
            self.info_bar,
            text="",
            font=("Zalando Sans Expanded SemiBold", 12),
            anchor="w",
            corner_radius=0,
        )
        self.status_label.pack(side="left", padx=(0, 12))
        self.viewer = Preview(self.workspace)
        self.viewer.pack(fill="both", expand=True)
        self.loading_logo = LoadingLogo(self.viewer)
        self.progress = ctk.CTkProgressBar(
            self.main, height=4, progress_color="#C26AAA"
        )
        self.progress.grid(row=2, column=0, sticky="ew", padx=9)
        self.progress.set(0)
        self.bottom = ctk.CTkFrame(self.main, corner_radius=0)
        self.bottom.grid(row=3, column=0, sticky="ew", padx=9, pady=(0, 7))
        self.bottom.grid_columnconfigure(0, weight=1)
        self.message = ctk.CTkLabel(
            self.bottom, text="", anchor="w", font=("Red Hat Display", 11)
        )
        self.message.grid(row=0, column=0, sticky="ew", padx=8)
        self.language = ctk.CTkSegmentedButton(
            self.bottom,
            values=["eng", "ind"],
            command=self.change_language,
            width=94,
            font=("Red Hat Display", 12),
            selected_color="#C26AAA",
        )
        self.language.grid(row=0, column=1, padx=7, pady=5)
        self.theme = ctk.CTkSegmentedButton(
            self.bottom,
            values=["dark", "light"],
            command=self.change_theme,
            width=105,
            font=("Red Hat Display", 12),
            selected_color="#C26AAA",
        )
        self.theme.grid(row=0, column=2, padx=(0, 6))
        self._keyboard_navigation = False
        self.bind(
            "<KeyPress>",
            lambda e: (
                setattr(self, "_keyboard_navigation", True)
                if e.keysym in ("Tab", "Up", "Down", "Left", "Right")
                else None
            ),
            add="+",
        )
        self.bind(
            "<ButtonPress>",
            lambda e: setattr(self, "_keyboard_navigation", False),
            add="+",
        )
        self.bind("<Control-o>", lambda e: self.choose_photo())
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Escape>", self.escape)
        self.bind("<Control-v>", self.paste_image)
        self.bind("<Control-V>", self.paste_image)
        if IS_MAC:
            self.bind("<Command-o>", lambda e: self.choose_photo())
            self.bind("<Command-s>", lambda e: self.save())
            self.bind("<Command-v>", self.paste_image)
        self.bind("<ButtonPress-1>", self.dismiss_quality_outside, add="+")
        self.bind(
            "<Return>",
            lambda e: (
                self.start() if self.modal is None and self.popup is None else None
            ),
        )
        self.apply_theme()
        self.update_controls()
        self.after(80, self.poll)
        self.file_drop = PhotoDrop(self, self.dropped_files, self.show_drop_feedback)

        def detect():
            from lena_gpu import adapters

            self.events.put(("devices", adapters()))

        threading.Thread(target=detect, daemon=True).start()
        # Do not maximize/map the root here. On Windows, state('zoomed') can
        # register the hidden root in the taskbar even while alpha=0, causing
        # the startup icon to flash, disappear, then reappear. The final reveal
        # performs the maximize exactly once.
        if not self.settings.get("onboarded"):
            self._onboarding_job = self.after(350, self.language_dialog)

    def report_callback_exception(self, kind, value, tb):
        from lena_diagnostics import exception

        exception(kind, value, tb)

    def t(self, key):
        value = COPY.get(key, (key, key))[0 if self.lang == "id" else 1]
        return value.replace("Ctrl+", "Cmd+") if IS_MAC else value

    def persist(self):
        self.settings.pop("category", None)
        self.settings.pop("model", None)
        self.settings.update(
            language=self.lang,
            theme="dark" if self.dark else "light",
            mode=self.mode,
            quality=self.selected,
        )
        try:
            save_settings(self.settings)
        except OSError:
            pass

    def button(self, parent, text, command, width=120, color=None):
        return MotionButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=32,
            corner_radius=10,
            font=("Red Hat Display Medium", 13),
            fg_color=color or ("#50535B" if self.dark else "#A6A6A8"),
            hover_color="#9C5793" if color is None else "#956196",
            text_color="#FFFFFF",
        )

    def icon(self, name, size_=22):
        mode = "dark" if self.dark else "light"
        return ctk.CTkImage(
            Image.open(ROOT / f"assets/icons/{name}-{mode}.png"), size=(size_, size_)
        )

    def apply_theme(self):
        # CTk restores focus after recoloring the title bar; use the root while
        # theme-specific sidebar widgets are being rebuilt.
        self.focus_set()
        ctk.set_appearance_mode("dark" if self.dark else "light")
        base = "#121316" if self.dark else "#F5F5F7"
        bar = "#191A1F" if self.dark else "#F5F5F7"
        surface = "#1D1E23" if self.dark else "#FFFFFF"
        self.main.configure(fg_color=base)
        self.workspace.configure(fg_color=surface)
        self.info_bar.configure(fg_color=surface)
        self.toolbar.configure(fg_color=bar)
        self.bottom.configure(fg_color=base)
        self.configure(fg_color=base)
        self.viewer.dark = self.dark
        self.viewer.empty = self.t("empty")
        self.viewer.hint = self.t("zoom_hint")
        self.viewer.schedule()
        self.viewer.empty_title_text = (
            "Mulai dari satu foto." if self.lang == "id" else "Start with a photo."
        )
        self.viewer.empty_button.configure(
            text=self.t("photo"), fg_color="#9164B5", hover_color="#A578C7"
        )
        self.settings_button.configure(image=self.icon("settings"), fg_color=bar)
        self.guide_button.configure(image=self.icon("guide"), fg_color=bar)
        self.language.configure(fg_color=("#E8E8ED", "#25262C"))
        self.theme.configure(fg_color=("#E8E8ED", "#25262C"))
        self.language.set("ind" if self.lang == "id" else "eng")
        self.theme.set("dark" if self.dark else "light")
        self.draw_sidebar()
        if self.busy and not self.download_active:
            self.loading_logo.start(
                self.dark, round(64 * self.sidebar._get_widget_scaling())
            )

    def change_theme(self, value):
        self.dark = value == "dark"
        self.dismiss_popup()
        self.apply_theme()
        self.persist()

    def change_language(self, value):
        # Only the sidebar's strings depend on language, not its geometry,
        # colors, or images -- so this updates text in place instead of
        # going through apply_theme(), which always rebuilds the whole
        # sidebar from scratch (and briefly flashed half-drawn controls).
        self.lang = "id" if value == "ind" else "en"
        self.dismiss_popup()
        self.language.set("ind" if self.lang == "id" else "eng")
        self.viewer.empty = self.t("empty")
        self.viewer.hint = self.t("zoom_hint")
        self.viewer.schedule()
        self.viewer.empty_title_text = (
            "Mulai dari satu foto." if self.lang == "id" else "Start with a photo."
        )
        self.viewer.empty_button.configure(text=self.t("photo"))
        self.retranslate_sidebar()
        self.persist()
        self.update_controls()

    def responsive(self, event=None):
        if not hasattr(self, "guide_button"):
            return
        compact = self.main.winfo_width() < 780
        self.save_button.configure(width=90 if compact else 112)
        if self.popup:
            self.dismiss_popup()

    def pick_quality(self, model):
        if self.busy or model not in dict(QUALITIES) or path(model) is None:
            return
        self.selected = model
        self.dismiss_popup()
        self.persist()
        self.refresh_sidebar_selection()

    def toggle_hair(self):
        if self.busy or path(REFINER) is None:
            return
        self.hair_fur = not self.hair_fur
        self.refresh_sidebar_selection()

    def dismiss_quality_outside(self, event):
        if not self.popup:
            return
        widget = event.widget
        while widget is not None:
            if widget is self.popup or widget is getattr(self, "quality_button", None):
                return
            widget = getattr(widget, "master", None)
        self.dismiss_popup()

    def update_controls(self):
        self.save_button.configure(
            state="normal" if self.result is not None and not self.busy else "disabled"
        )
        self.draw_sidebar()

    def dismiss_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def choose_photo(self):
        if self.busy or self.modal is not None:
            return
        filename = filedialog.askopenfilename(
            parent=self,
            title=self.t("photo").lstrip("+ "),
            filetypes=[
                ("Photos", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        self.load_photo(filename)

    def dropped_files(self, filenames):
        if self.busy or self.modal is not None:
            return
        supported = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
        filename = next(
            (name for name in filenames if Path(name).suffix.lower() in supported), None
        )
        if filename:
            self.load_photo(filename)
        elif filenames:
            messagebox.showerror(
                self.t("error_title"), self.t("photo_error"), parent=self
            )

    def paste_image(self, event=None):
        if self.busy or self.modal is not None:
            return "break"
        try:
            content = ImageGrab.grabclipboard()
            if isinstance(content, Image.Image):
                self.source = ImageOps.exif_transpose(content).convert("RGBA")
                self.source_name = "clipboard"
                self.result = None
                self.dismiss_popup()
                self.viewer.set_images(self.source, reset=True)
                self.status("")
                self.update_controls()
            elif isinstance(content, list):
                self.dropped_files(content)
            else:
                self.status(self.t("clipboard_empty"))
        except (OSError, ValueError, Image.DecompressionBombError):
            self.status(self.t("photo_error"))
        return "break"

    def show_drop_feedback(self, active):
        self.viewer.configure(
            highlightthickness=2 if active else 0, highlightbackground="#78B7E8"
        )
        if active:
            self.viewer.placeholder.configure(text=self.t("drop_hint"))
            self.viewer.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.viewer.placeholder.lift()
        else:
            self.viewer.schedule()

    def load_photo(self, filename):
        if self.busy:
            return
        try:
            with Image.open(filename) as im:
                self.source = ImageOps.exif_transpose(im).convert("RGBA")
            self.source_name = Path(filename).stem
            self.result = None
            self.dismiss_popup()
            self.viewer.set_images(self.source, reset=True)
            self.status("")
            self.update_controls()
        except (OSError, ValueError, Image.DecompressionBombError):
            messagebox.showerror(
                self.t("error_title"), self.t("photo_error"), parent=self
            )

    def clear(self):
        if self.busy:
            self.cancel.set()
            return
        from lena_worker import shutdown

        shutdown()
        self.source = self.result = None
        self.viewer.set_images(None, reset=True)
        self.status("")
        self.update_controls()
        self.after_idle(_trim_process_memory)

    def status(self, text):
        self.status_text = text
        self.message.configure(text=text)
        if getattr(self, "status_timer", None):
            self.after_cancel(self.status_timer)
            self.status_timer = None
        if text == self.t("saved"):
            self.status_timer = self.after(4000, lambda: self.status(""))

    def begin(self, download=False):
        if self.busy:
            return False
        self._processing_stage = ""
        self._matting_warning = False
        self._result_warning = False
        if hasattr(self, "validation_warnings") and hasattr(self, "task"):
            self.validation_warnings[self.task] = False
        if not download:
            self.result = None
            self.viewer.set_images(self.source, reset=True)
            self.viewer.render()
        self.busy = True
        self.download_active = download
        self.cancel.clear()
        self.started = time.monotonic()
        self.dismiss_popup()
        self.update_controls()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        if not download:
            self.loading_logo.start(
                self.dark, round(64 * self.sidebar._get_widget_scaling())
            )
        return True

    def report(self, kind, value):
        self.events.put((kind, value))

    def start(self):
        if self.busy:
            self.cancel.set()
            return
        if path(self.selected) is None:
            return
        self.infer(self.selected)

    def infer(self, model, prepare_missing=False):
        if self.source is None:
            self.choose_photo()
            return
        missing = path(model) is None
        if missing and not prepare_missing:
            self.download_models([model])
            return
        if not self.begin():
            return
        if missing:
            self.download_active = True
            self.loading_logo.stop()
        # Inputs are loaded RGBA images and remain unchanged while busy.
        # Keep a reference instead of duplicating the full bitmap on the UI thread.
        photo = self.source
        mode = self.mode
        devices = list(self.devices)
        hair_fur = self.hair_fur
        from lena_diagnostics import record

        record("inference_start", model=model, mode=mode, size=photo.size)

        def work():
            try:
                if missing:
                    self.report("model_label", (MODELS[model][0], 1, 1))
                    prepare(model, self.report, self.cancel)
                    if self.cancel.is_set():
                        raise Cancelled()
                    self.report("inference_downloaded", None)
                from lena_worker import process

                output, backend, fallback = process(
                    photo,
                    model,
                    mode,
                    devices,
                    self.report,
                    self.cancel,
                    hair_fur=hair_fur,
                )
                self.report("result", (output, backend, fallback))
            except Cancelled:
                self.report("cancelled", None)
            except Exception as error:
                self.report("error", str(error))

        threading.Thread(target=work, daemon=True).start()

    def download_models(self, models):
        models = [model for model in models if path(model) is None]
        if not models:
            return
        if not self.begin(download=True):
            return

        def work():
            try:
                for index, model in enumerate(models):
                    self.report(
                        "model_label", (MODELS[model][0], index + 1, len(models))
                    )
                    prepare(model, self.report, self.cancel)
                self.report("ready", None)
            except Cancelled:
                self.report("cancelled", None)
            except Exception as error:
                self.report("error", str(error))

        threading.Thread(target=work, daemon=True).start()

    def finish(self):
        self.loading_logo.stop()
        self.busy = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.status_label.configure(text="")
        self.update_controls()

    def poll(self):
        # Keep polling alive even if an individual UI callback raises.
        if getattr(self, "_poll_job", None):
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(100, self.poll)
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "devices":
                    self.devices = value
                elif kind == "backend":
                    self.status(value)
                elif kind == "stage":
                    self._processing_stage = value
                    self.status(
                        "Refining Hair" if value == "matting" else self.t(value)
                    )
                    from lena_diagnostics import record

                    record("stage", stage=value)
                elif kind == "matting_warning":
                    self._matting_warning = True
                elif kind == "validation_warning":
                    self._result_warning = bool(value)
                    if hasattr(self, "validation_warnings") and hasattr(self, "task"):
                        self.validation_warnings[self.task] = bool(value)
                elif kind == "model_label":
                    self.active_download = value[0]
                    self.status(f"{value[0]}  ·  {value[1]}/{value[2]}")
                elif kind in ("upscale_downloaded", "inference_downloaded"):
                    self.download_active = False
                    self.loading_logo.start(
                        self.dark, round(64 * self.sidebar._get_widget_scaling())
                    )
                elif kind == "download":
                    n, total = value
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress.set(n / total if total else 0)
                    self.status_label.configure(
                        text=(
                            f"DOWNLOAD  {n/1e6:.0f} / {total/1e6:.0f} MB"
                            if total
                            else f"DOWNLOAD  {n/1e6:.0f} MB"
                        )
                    )
                    if hasattr(self, "manager_progress"):
                        self.manager_progress(n, total)
                elif kind == "tile_progress":
                    n, total = value
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress.set(n / total)
                    self.status(f"Upscale · {n}/{total} · {n/total:.0%}")
                elif kind == "result":
                    self.result = value[0]
                    self.viewer.set_images(self.source, self.result)
                    elapsed = time.monotonic() - self.started
                    self.finish()
                    message = f'{self.t("done")} · {elapsed:.1f}s · {value[1]}'
                    if self._matting_warning:
                        message += " · " + (
                            "Refinement rambut tidak tersedia; hasil awal dipertahankan."
                            if self.lang == "id"
                            else "Hair refinement unavailable; original cutout kept."
                        )
                    self.status(message)
                    from lena_diagnostics import record

                    record(
                        "result_shown",
                        size=self.result.size,
                        matting_fallback=self._matting_warning,
                    )
                    self.after(700, self.trim_memory_after_preview)
                elif kind == "ready":
                    self.finish()
                    self.status(self.t("ready"))
                elif kind == "cancelled":
                    self.finish()
                    self.status(self.t("cancelled"))
                elif kind == "error":
                    # A full disk or protected log path must not strand the UI
                    # in busy state or stop its event polling permanently.
                    try:
                        HOME.mkdir(parents=True, exist_ok=True)
                        (HOME / "app-error.log").write_text(value, encoding="utf-8")
                    except OSError:
                        pass
                    downloading = self.download_active
                    model_name = getattr(self, "active_download", "")
                    self.finish()
                    self.status(self.t("error_title"))
                    if not self._closing:
                        reason = value.split(" for url:", 1)[0][:180] if value else ""
                        message = (
                            self.t("download_error").format(
                                model=model_name or "Model", reason=reason
                            )
                            if downloading
                            else self.t("error")
                        )
                        messagebox.showerror(
                            self.t("error_title"), message, parent=self
                        )
        except queue.Empty:
            pass
        if self.busy and not self.download_active:
            self.status_label.configure(
                text=f"PROCESSING  {time.monotonic()-self.started:.0f}s"
            )

    def trim_memory_after_preview(self, attempt=0):
        """Trim only after the async preview no longer owns temporary frames."""
        viewer = getattr(self, "viewer", None)
        future = getattr(viewer, "_future", None) if viewer is not None else None
        if future is not None and not future.done() and attempt < 30:
            self.after(50, lambda: self.trim_memory_after_preview(attempt + 1))
            return
        _trim_process_memory()

    def save(self):
        if self.result is None or self.busy:
            return
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Save PNG",
            initialfile=self.source_name + "-LENA.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
        )
        if filename:
            try:
                self.result.save(filename, "PNG")
                self.status(self.t("saved"))
            except OSError:
                messagebox.showerror(
                    self.t("error_title"), self.t("save_error"), parent=self
                )

    def dialog(self, title, width=630, height=460):
        self.dismiss_popup()
        if self.modal:
            self.modal.destroy()
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.transient(self)
        win.resizable(True, True)
        scale = win._get_window_scaling()
        width = min(width, int((self.winfo_screenwidth() - 60) / scale))
        height = min(height, int((self.winfo_screenheight() - 100) / scale))
        x = max(
            0,
            min(
                self.winfo_screenwidth() - round(width * scale),
                self.winfo_rootx() + (self.winfo_width() - round(width * scale)) // 2,
            ),
        )
        y = max(
            0,
            min(
                self.winfo_screenheight() - round(height * scale) - 40,
                self.winfo_rooty() + (self.winfo_height() - round(height * scale)) // 2,
            ),
        )
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.minsize(min(460, width), min(300, height))
        self.modal = win

        def closed():
            self.modal = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", closed)
        win.after(80, win.grab_set)
        win.after(80, win.focus_force)
        body = ctk.CTkScrollableFrame(win, corner_radius=0)
        body.pack(fill="both", expand=True, padx=15, pady=15)

        def center():
            if not win.winfo_exists():
                return
            if win.winfo_width() < 10 or win.winfo_height() < 10:
                win.after(50, center)
                return
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            if os.name == "nt":
                screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            border_x = win.winfo_rootx() - win.winfo_x()
            border_y = win.winfo_rooty() - win.winfo_y()
            left = max(
                0,
                min(
                    screen_w - win.winfo_width(),
                    self.winfo_rootx()
                    + (self.winfo_width() - win.winfo_width()) // 2
                    - border_x,
                ),
            )
            top = max(
                0,
                min(
                    screen_h - win.winfo_height() - 40,
                    self.winfo_rooty()
                    + (self.winfo_height() - win.winfo_height()) // 2
                    - border_y,
                ),
            )
            win.geometry(f"+{left}+{top}")

        win.after(120, center)
        fade_window(win)
        return win, body, closed

    def language_dialog(self):
        win, body, closed = self.dialog("Choose your language", 470, 300)
        ctk.CTkLabel(
            body, text="LENA", font=("Zalando Sans Expanded SemiBold", 30)
        ).pack(pady=(20, 8))
        ctk.CTkLabel(
            body, text="Choose your language", font=("Red Hat Display", 21)
        ).pack(pady=12)

        def choose(lang):
            self.change_language(lang)
            closed()
            self.after(100, self.welcome_dialog)

        for label, lang in [("English", "eng"), ("Indonesia", "ind")]:
            self.button(
                body, label, lambda l=lang: choose(l), width=210, color="#C26AAA"
            ).pack(pady=5)
        win.protocol(
            "WM_DELETE_WINDOW", lambda: choose("ind" if self.lang == "id" else "eng")
        )

    def open_settings(self):
        win, body, closed = self.dialog(self.t("settings"), 600, 485)
        ctk.CTkLabel(
            body, text=self.t("settings"), font=("Red Hat Display SemiBold", 25)
        ).pack(anchor="w", padx=12, pady=10)
        self.radio_mode = tk.StringVar(value=self.mode)

        def change():
            self.mode = self.radio_mode.get()
            self.persist()

        for value, key in [("auto", "auto"), ("cpu", "cpu")]:
            ctk.CTkRadioButton(
                body,
                text=self.t(key),
                variable=self.radio_mode,
                value=value,
                command=change,
                font=("Red Hat Display", 15),
            ).pack(anchor="w", padx=16, pady=9)
        info = (
            self.t("dml")
            + "\n\n"
            + (
                "\n".join(d["name"] for d in self.devices)
                if self.devices
                else self.t("no_gpu")
            )
        )
        from lena_safety import read_state

        if read_state().get("devices"):
            info += "\n\n" + self.t("gpu_safe")
        ctk.CTkLabel(
            body,
            text=info,
            wraplength=510,
            justify="left",
            font=("Red Hat Display", 14),
        ).pack(fill="x", padx=15, pady=15)
        self.button(body, self.t("models_folder"), self.open_cache, width=190).pack(
            anchor="w", padx=15, pady=8
        )
        ctk.CTkLabel(
            body,
            text="LENA 1.0 · by Hiratsani ©2026\n" + self.t("offline"),
            wraplength=510,
            justify="left",
            font=("Red Hat Display", 12),
        ).pack(fill="x", padx=15, pady=15)
        self.button(
            body,
            "Licenses",
            lambda: open_local(ROOT / "THIRD-PARTY-NOTICES.txt"),
            width=100,
        ).pack(anchor="w", padx=15, pady=5)

    def open_cache(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        open_local(CACHE)

    def open_guide(self):
        win, body, closed = self.dialog(self.t("guide"), 620, 560)
        ctk.CTkLabel(
            body, text=self.t("guide"), font=("Red Hat Display SemiBold", 25)
        ).pack(anchor="w", padx=15, pady=12)
        for key in ("steps", "once", "offline"):
            ctk.CTkLabel(
                body,
                text=self.t(key),
                font=("Red Hat Display", 15),
                wraplength=535,
                justify="left",
            ).pack(fill="x", padx=15, pady=12)

    def donate(self):
        webbrowser.open("https://saweria.co/hiratsani")

    def escape(self, event=None):
        # Custom Settings / Guide / Coffee dialogs must always be dismissible
        # with Escape, even if Windows returned focus to the owner after Alt+Tab.
        modal = getattr(self, "modal", None)
        if modal is not None and getattr(modal, "_lena_kind", None) in (
            "settings",
            "guide",
            "support",
        ):
            try:
                modal.close_panel()
            except (tk.TclError, AttributeError):
                pass
            return "break"
        if self.popup:
            self.dismiss_popup()
            return "break"
        elif self.busy:
            self.cancel.set()
            return "break"

    def close(self):
        from lena_diagnostics import record

        if not self._closing:
            record("close_requested", busy=self.busy)
        self._closing = True
        self.cancel.set()
        self.persist()
        if self.busy:
            self.withdraw()
            self.after(150, self.close)
        else:
            from lena_worker import shutdown

            shutdown()
            if getattr(self, "_poll_job", None):
                self.after_cancel(self._poll_job)
                self._poll_job = None
            record("clean_exit")
            self.destroy()


if __name__ == "__main__":
    from lena_custom import EnhancedApp

    EnhancedApp().mainloop()
