"""Current Enhanced application using the supplied Illustrator layout."""

import os, ctypes, threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image
from tkinter import messagebox, filedialog
from lena_app import App
from lena_design import DesignSidebar, ModeSwitch, transfer_art
from lena_redesign import RedesignedPanels as Panels
from lena_scroll import WheelRouter
from lena_models import path
from lena_upscale import MODEL, output_size
from lena_downloads import prepare, Cancelled
import lena_enhanced_text  # Registers the workspace's extra localized labels.


class ChromeButton(ctk.CTkButton):
    """Use CTk's full-surface redraw with room for compact chrome content."""

    def _create_grid(self):
        super()._create_grid()
        if self._image is not None and not self._text:
            self.grid_columnconfigure((0, 4), minsize=0)
        elif self._text:
            self.grid_columnconfigure((0, 4), minsize=self._apply_widget_scaling(8))


def jpeg_image(image, background):
    """Flatten an image against any Pillow-compatible background color."""
    result = Image.new("RGB", image.size, background)
    if "A" in image.getbands():
        result.paste(image.convert("RGB"), mask=image.getchannel("A"))
    else:
        result.paste(image.convert("RGB"))
    return result


class EnhancedApp(DesignSidebar, Panels, App):
    def chrome_button(
        self,
        parent,
        text,
        command,
        width,
        *,
        height=36,
        blue=False,
        font_size=12,
        icon=None,
    ):
        header = parent is getattr(self, "save_group", None)
        background = (
            ("#191A1F" if self.dark else "#F5F5F7")
            if header
            else ("#121316" if self.dark else "#F5F5F7")
        )
        color = "#117AD3" if blue else ("#35373F" if self.dark else "#E1DEE6")
        hover = "#268CE6" if blue else ("#484A54" if self.dark else "#D0CBD7")
        return ChromeButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            corner_radius=height / 2,
            fg_color=color,
            bg_color=background,
            hover_color=hover,
            text_color="#FFFFFF" if self.dark or blue else "#24212B",
            font=("Red Hat Display Medium", font_size),
            image=self.icon(icon, 16) if icon else None,
        )

    def __init__(self):
        # App.__init__ calls apply_theme()/draw_sidebar before EnhancedApp has
        # finished replacing its chrome. Suppress those partial startup paints;
        # one final draw is performed after the enhanced layout is complete.
        self._suspend_sidebar_draw = True
        self.task = "remove"
        self.document_source = None
        self.results = {"remove": None, "upscale": None}
        self.task_sources = {"remove": None, "upscale": None}
        self.input_lineage = {"remove": frozenset(), "upscale": frozenset()}
        self.result_lineage = {"remove": frozenset(), "upscale": frozenset()}
        # Tracks whether the CURRENT result in each workspace has already been
        # forwarded to the opposite process. This prevents repeating the same
        # branch (e.g. Remove A -> Upscale, then sending Remove A again).
        self.result_forwarded = {"remove": False, "upscale": False}
        self.validation_warnings = {"remove": False, "upscale": False}
        self.preview_background = "transparent"
        self.choice_popup = None
        self.choice_trigger = None
        self.jpg_palette = None
        self.scale = 2
        self.enhanced_ready = False
        self.manager_rows = {}
        self.manager_window = None
        self.active_download = None
        self._panel_job = None
        super().__init__()
        # The base app schedules onboarding before this window has been mapped
        # and maximized. Position the chooser only after the first full reveal.
        self._onboarding_pending = not self.settings.get("onboarded")
        if self._onboarding_pending:
            self.after_cancel(self._onboarding_job)
        self.sidebar.pack_propagate(False)
        self.sidebar.configure(width=295)
        self.title("LENA 1.0")
        self.side_scroll.pack_forget()
        self.mode_header = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.mode_header.grid(row=0, column=0, sticky="w", padx=12)
        self.remove_label = ctk.CTkLabel(
            self.mode_header, text="REMOVE\nBACKGROUND", font=("Red Hat Display", 10)
        )
        self.remove_label.pack(side="left", padx=(0, 6))
        scale = self.sidebar._get_widget_scaling() * 0.70
        self.mode_switch = ModeSwitch(
            self.mode_header,
            Image.new("RGB", (round(110.1 * scale), round(37.6 * scale)), "#202730"),
            scale,
            lambda: self.switch_task("upscale" if self.task == "remove" else "remove"),
        )
        self.mode_switch.pack(side="left")
        self.up_label = ctk.CTkLabel(
            self.mode_header, text="IMAGE\nUPSCALER", font=("Red Hat Display", 10)
        )
        self.up_label.pack(side="left", padx=(6, 0))
        self.remove_label.configure(cursor="hand2")
        self.up_label.configure(cursor="hand2")
        self.remove_label.bind("<Button-1>", lambda e: self.switch_task("remove"))
        self.up_label.bind("<Button-1>", lambda e: self.switch_task("upscale"))
        self.save_button.destroy()
        self.save_group = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.save_group.grid(row=0, column=2, sticky="e", padx=12, pady=10)
        self.models_button = self.chrome_button(
            self.save_group, "AI Model", self.open_models, 88, height=32
        )
        self.models_button.pack(side="left", padx=(0, 10))
        self.save_button = self.chrome_button(
            self.save_group, "↓ Save PNG", self.save, 100, height=32, blue=True
        )
        self.save_button.pack(side="left")
        self.jpg_button = self.chrome_button(
            self.save_group, "JPG", self.save_jpg, 48, height=32, blue=True
        )
        self.jpg_button.pack(side="left", padx=(10, 0))
        self.settings_button.destroy()
        self.guide_button.destroy()
        self.controls.grid_remove()
        self.message.grid_configure(row=1, column=0, columnspan=4, pady=(0, 2))
        # Keep App's segmented controls alive but hidden for state compatibility;
        # the visible footer now uses compact buttons with upward popovers.
        self.language.grid_remove()
        self.theme.grid_remove()
        for control in (self.language, self.theme):
            control.configure(
                width=94,
                height=24,
                fg_color=("#CDCDCE", "#141920"),
                selected_color=("#85888D", "#686B71"),
                selected_hover_color=("#777A80", "#777A80"),
            )
        self.footer_actions = ctk.CTkFrame(self.bottom, fg_color="transparent")
        self.footer_actions.grid(row=0, column=2, sticky="e", padx=(8, 4), pady=10)
        self.donation.destroy()
        self.info_bar.pack_forget()
        self.donation = self.chrome_button(
            self.footer_actions, "☕ Buy Me A Coffee", self.donate, 124, font_size=11
        )
        self.donation.pack(side="left", padx=(0, 8))
        self.settings_button = self.chrome_button(
            self.footer_actions, "", self.open_settings, 36, icon="settings"
        )
        self.settings_button.pack(side="left", padx=(0, 8))
        self.guide_button = self.chrome_button(
            self.footer_actions, "", self.open_guide, 36, icon="guide"
        )
        self.guide_button.pack(side="left", padx=(0, 8))
        self.preferences_button = self.chrome_button(
            self.footer_actions,
            "🌐  │  ☀",
            self.open_preferences_menu,
            88,
            font_size=14,
        )
        self.preferences_button.configure(font=("Segoe UI Symbol", 14))
        self.preferences_button.pack(side="left")
        self.transfer_group = ctk.CTkFrame(self.bottom, fg_color="transparent")
        self.transfer_group.grid(row=0, column=0, sticky="ew", padx=5, pady=10)
        self.transfer_group.grid_columnconfigure(2, weight=1)
        self.transfer = self.button(
            self.transfer_group, "", self.send_result, width=220, color="#141920"
        )
        self.transfer.grid(row=0, column=0, sticky="w")
        self.transfer.art_only_hover = True
        self.preview_button = self.button(
            self.transfer_group, "", self.open_preview_menu, width=178, color="#25262A"
        )
        self.preview_button.configure(
            height=30, corner_radius=15, font=("Red Hat Display Medium", 11)
        )
        self.preview_button.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.preview_button.grid_remove()
        self.transfer_hint = ctk.CTkLabel(
            self.transfer_group,
            text="",
            font=("Red Hat Display", 10),
            wraplength=210,
            justify="left",
            anchor="w",
        )
        self.transfer_hint.grid(row=0, column=2, sticky="w", padx=(9, 0))
        self.transfer_hint.grid_remove()
        self.result_warning = ctk.CTkFrame(
            self.workspace,
            corner_radius=12,
            fg_color="#302936",
            border_width=1,
            border_color="#8D6A98",
        )
        self.result_warning_label = ctk.CTkLabel(
            self.result_warning, text="", font=("Red Hat Display Medium", 12)
        )
        self.result_warning_label.pack(side="left", padx=(12, 7), pady=7)
        self.try_best_button = self.button(
            self.result_warning, "", self.try_best_quality, width=130, color="#865AA3"
        )
        self.try_best_button.pack(side="left", padx=(0, 7), pady=5)
        saved_preview = str(
            self.settings.get("preview_background", "transparent")
        ).lower()
        self.preview_background = (
            saved_preview
            if saved_preview in ("transparent", "white", "black")
            else "transparent"
        )
        self.viewer.set_background(self.preview_background)
        self.enhanced_ready = True
        self._transfer_key = None
        self.wheel_router = WheelRouter(self)
        # Everything that changes sidebar geometry is now installed. Flush the
        # maximized geometry, then allow exactly the complete design to render.
        self._suspend_sidebar_draw = False
        self.update_idletasks()
        self._design_layout = None
        self.apply_theme()
        self.update_controls()
        self.status("")
        self.responsive()

        # Build the complete initial chrome while the root is still withdrawn.
        # The final Windows maximize is intentionally deferred to the reveal so
        # the taskbar button is registered only once.
        def settle_initial_sidebar():
            if not self.winfo_exists():
                return
            self.update_idletasks()
            self._design_layout = None
            self.draw_sidebar()
            self.responsive()
            self.update_idletasks()
            self._reveal_startup_window()

        self.after(160, settle_initial_sidebar)
        if os.name == "nt" and ctypes.windll.shell32.IsUserAnAdmin():
            self.after(600, lambda: self.status(self.t("admin_hint")))

    def _reveal_startup_window(self):
        if not getattr(self, "_startup_reveal_pending", False):
            return
        self._startup_reveal_pending = False
        try:
            # Alpha is already zero, but set it again before mapping so DWM can
            # never present an unfinished frame. Deiconify only once: this is
            # also the first moment Windows is allowed to create LENA's taskbar
            # button.
            self.attributes("-alpha", 0.0)
            self.deiconify()
            if getattr(self, "_startup_target_zoomed", False):
                self.state("zoomed")
            self.update_idletasks()

            # Maximizing changes the available client size. Perform one final
            # atomic layout pass while still invisible, then fade in.
            self._design_layout = None
            self.draw_sidebar()
            self.responsive()
            self.update_idletasks()
            self.lift()
        except tk.TclError:
            return

        # CTk draws several controls through Canvas/after_idle callbacks.  A
        # window can therefore have correct geometry while a few rounded
        # rectangles/icons are still waiting for their first real paint.  Keep
        # the mapped/maximized root fully invisible for two idle turns plus a
        # tiny DWM settle window before beginning the fade.  This removes the
        # blocky first-frame flash without showing a fake splash screen or
        # adding heavyweight startup work.
        def begin_fade():
            if not self.winfo_exists():
                return
            try:
                self.update_idletasks()
                self._design_layout = None
                self.draw_sidebar()
                self.responsive()
                self.update_idletasks()
            except tk.TclError:
                return

            total = 7

            def fade(step=0):
                if not self.winfo_exists():
                    return
                t = min(1, step / total)
                # Smooth cubic ease-out: fast enough to feel instant, but the
                # first visible frame is already the fully painted interface.
                eased = 1 - (1 - t) ** 3
                try:
                    self.attributes("-alpha", eased)
                except tk.TclError:
                    return
                if step < total:
                    self.after(11, lambda: fade(step + 1))
                else:
                    try:
                        self.attributes("-alpha", 1.0)
                    except tk.TclError:
                        pass
                    if getattr(self, "_onboarding_pending", False):
                        self._onboarding_pending = False
                        self.after(30, self.language_dialog)

            fade()

        def second_idle_pass():
            if not self.winfo_exists():
                return
            try:
                self.update_idletasks()
            except tk.TclError:
                return
            # Give Windows/DWM and CustomTkinter's deferred Canvas work one
            # short frame to settle while alpha remains exactly zero.
            self.after(45, begin_fade)

        self.after_idle(lambda: self.after_idle(second_idle_pass))

    def responsive(self, event=None):
        super().responsive(event)
        if hasattr(self, "message"):
            self.message.configure(
                wraplength=max(
                    170, self.main.winfo_width() / self.main._get_widget_scaling() - 35
                )
            )
        if not getattr(self, "enhanced_ready", False):
            return
        if self.save_button.cget("width") != 100:
            self.save_button.configure(width=100)
        compact = self.main.winfo_width() / self.main._get_widget_scaling() < 720
        changed = getattr(self, "_compact_chrome", None) != compact
        self._compact_chrome = compact
        self.toolbar.grid_columnconfigure((0, 1, 2), weight=0, uniform="")
        self.toolbar.grid_columnconfigure(1, weight=1)
        if changed:
            if compact:
                self.bottom.grid_columnconfigure((0, 1, 2), weight=0, uniform="")
                self.bottom.grid_columnconfigure(0, weight=1)
                self.mode_header.grid_configure(
                    row=0, column=0, columnspan=3, pady=(8, 0)
                )
                self.save_group.grid_configure(
                    row=1, column=2, columnspan=1, sticky="e", padx=12, pady=8
                )
                self.transfer_group.grid_configure(
                    row=0, column=0, columnspan=3, sticky="ew"
                )
                self.footer_actions.grid_configure(
                    row=1, column=0, columnspan=3, sticky="e"
                )
                self.message.grid_configure(row=2, column=0, columnspan=3)
            else:
                # The old equal-width footer forced the transfer area into exactly
                # one third of the window. Long English/Indonesian strings were
                # then clipped even though there was plenty of free space in the
                # middle. Give the transfer side all remaining width and keep the
                # right-side controls at their natural size.
                self.bottom.grid_columnconfigure((0, 1, 2), weight=0, uniform="")
                self.bottom.grid_columnconfigure(0, weight=1)
                self.mode_header.grid_configure(row=0, column=0, columnspan=1, pady=0)
                self.save_group.grid_configure(
                    row=0, column=2, columnspan=1, sticky="e", padx=12, pady=10
                )
                self.transfer_group.grid_configure(
                    row=0, column=0, columnspan=2, sticky="ew"
                )
                self.footer_actions.grid_configure(
                    row=0, column=2, columnspan=1, sticky="e"
                )
                self.message.grid_configure(row=1, column=0, columnspan=3)
        self._layout_transfer_footer()
        # grid_configure remaps a grid_remove'd label during startup/maximize.
        # An empty status must not reserve an invisible extra footer row.
        if not self.message.cget("text"):
            self.message.grid_remove()

    def _fit_preview_button(self, text):
        """Size the preview selector from its translated text instead of a fixed box."""
        self.preview_button.configure(text=text)
        measured = None
        try:
            self.preview_button.update_idletasks()
            label = getattr(self.preview_button, "_text_label", None)
            if label is not None:
                scale = max(0.25, float(self.preview_button._get_widget_scaling()))
                measured = label.winfo_reqwidth() / scale
        except (tk.TclError, TypeError, ValueError, AttributeError):
            measured = None
        if measured is None or measured <= 1:
            measured = len(text) * 6.6
        self.preview_button.configure(width=max(150, min(300, round(measured + 30))))

    def _desktop_transfer_wraplength(self, preview_ready):
        """Use the real leftover footer width instead of a fixed wrap box."""
        scale = max(0.25, float(self.main._get_widget_scaling()))
        try:
            self.transfer_group.update_idletasks()
        except tk.TclError:
            return 250
        group_width = self.transfer_group.winfo_width() / scale
        if group_width <= 1:
            group_width = max(260, self.main.winfo_width() / scale - 40)
        used = self.transfer.winfo_reqwidth() / scale
        if preview_ready:
            try:
                used += 12 + self.preview_button.winfo_reqwidth() / scale
            except tk.TclError:
                used += 190
        # Leave breathing room so the label does not kiss the buttons. A small
        # minimum keeps the Indonesian helper at two balanced lines instead of
        # dropping the final short word by itself.
        available = max(230, round(group_width - used - 30))
        return min(available, 420)

    def _layout_transfer_footer(self):
        """Keep transfer controls readable across language and window-size changes."""
        if not getattr(self, "enhanced_ready", False):
            return
        preview_ready = (
            self.task == "remove" and self.result is not None and not self.busy
        )
        has_hint = bool(self.transfer_hint.cget("text"))
        if preview_ready:
            self.preview_button.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=0)
        else:
            self.preview_button.grid_remove()
        if not has_hint:
            self.transfer_hint.grid_remove()
            return
        if getattr(self, "_compact_chrome", False):
            # On narrow windows the sentence gets its own row instead of being
            # squeezed to a few visible characters beside the buttons.
            width = max(
                180,
                round(
                    self.main.winfo_width() / max(0.25, self.main._get_widget_scaling())
                    - 28
                ),
            )
            self.transfer_hint.configure(wraplength=width)
            self.transfer_hint.grid(
                row=1, column=0, columnspan=3, sticky="w", padx=(2, 0), pady=(5, 0)
            )
        else:
            # Idle helper copy already contains a deliberate line break. Do not
            # let Tk wrap that second line again (which used to orphan "ini.").
            # Other, longer status messages still use the adaptive wrap width.
            hint_text = str(self.transfer_hint.cget("text"))
            wrap = (
                0
                if "\n" in hint_text
                else self._desktop_transfer_wraplength(preview_ready)
            )
            self.transfer_hint.configure(wraplength=wrap)
            self.transfer_hint.grid(
                row=0, column=2, columnspan=1, sticky="w", padx=(9, 0), pady=0
            )

    def persist(self):
        if hasattr(self, "settings"):
            self.settings.pop("smart_shadow", None)
            self.settings["preview_background"] = getattr(
                self, "preview_background", "transparent"
            )
        super().persist()

    def dismiss_choice_popup(self):
        panel = getattr(self, "choice_popup", None)
        self.choice_popup = None
        self.choice_trigger = None
        if panel is not None:
            try:
                panel.destroy()
            except tk.TclError:
                pass

    def _open_choice_menu(self, trigger, title, options, width=190):
        if self.busy:
            return
        if self.choice_popup is not None and self.choice_trigger is trigger:
            self.dismiss_choice_popup()
            return
        self.dismiss_choice_popup()
        self.dismiss_popup()
        self.dismiss_jpg_palette()
        height = 48 + sum(24 if command is None else 34 for _, _, command in options)
        scale = self._get_window_scaling()
        pixel_width = round(width * scale)
        pixel_height = round(height * scale)
        center = trigger.winfo_rootx() + trigger.winfo_width() / 2
        x = round(center - pixel_width / 2)
        y = round(trigger.winfo_rooty() - 7 * scale - pixel_height)
        left = self.winfo_rootx() + round(8 * scale)
        right = self.winfo_rootx() + self.winfo_width() - round(8 * scale)
        x = max(left, min(right - pixel_width, x))
        y = max(self.winfo_rooty() + round(8 * scale), y)

        # A normal child widget always owns a rectangular background, which
        # leaked through outside CTk's rounded corners over the image preview.
        # Use a color-keyed borderless window so those corner pixels are truly
        # transparent while the rounded panel stays fully interactive.
        chroma = "#010203"
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self)
        popup.configure(bg=chroma)
        popup.geometry(f"{pixel_width}x{pixel_height}+{x}+{y}")
        if os.name == "nt":
            popup.wm_attributes("-transparentcolor", chroma)
        popup.bind("<Escape>", self.escape)
        panel = ctk.CTkFrame(
            popup,
            width=width,
            height=height,
            corner_radius=12,
            fg_color="#292A30" if self.dark else "#FFFFFF",
            bg_color=chroma,
            border_width=1,
            border_color="#69636D" if self.dark else "#BBB7C1",
        )
        panel.pack(fill="both", expand=True)
        panel.pack_propagate(False)
        self.choice_popup = popup
        self.choice_trigger = trigger
        ink = "#F5F2F7" if self.dark else "#24212B"
        ctk.CTkLabel(
            panel,
            text=title,
            font=("Red Hat Display SemiBold", 13),
            text_color=ink,
            anchor="w",
        ).pack(fill="x", padx=11, pady=(9, 5))
        for label, selected, command in options:
            if command is None:
                ctk.CTkLabel(
                    panel,
                    text=label,
                    font=("Red Hat Display SemiBold", 11),
                    text_color="#B9B1C0" if self.dark else "#3F3944",
                    anchor="w",
                    height=20,
                ).pack(fill="x", padx=15, pady=(5, 0))
                continue
            row = ctk.CTkButton(
                panel,
                text=("✓  " if selected else "   ") + label,
                command=command,
                width=width - 16,
                height=30,
                corner_radius=8,
                anchor="w",
                font=("Red Hat Display Medium", 12),
                fg_color=(
                    ("#594264" if self.dark else "#E0D2E5")
                    if selected
                    else "transparent"
                ),
                hover_color="#45404E" if self.dark else "#E2DAE6",
                text_color=ink,
            )
            row.pack(fill="x", padx=8, pady=2)
        panel.update_idletasks()
        popup.deiconify()
        popup.lift()

    def open_preferences_menu(self):
        self._open_choice_menu(
            self.preferences_button,
            self.words("Tampilan", "Appearance"),
            [
                (self.t("language_button"), None, None),
                ("English", self.lang == "en", lambda: self.change_language("eng")),
                ("Indonesia", self.lang == "id", lambda: self.change_language("ind")),
                (self.t("theme_button"), None, None),
                ("Dark", self.dark, lambda: self.change_theme("dark")),
                ("Light", not self.dark, lambda: self.change_theme("light")),
            ],
            200,
        )

    def open_language_menu(self):
        self.open_preferences_menu()

    def open_theme_menu(self):
        self.open_preferences_menu()

    def open_preview_menu(self):
        labels = [
            ("transparent", "preview_transparent"),
            ("white", "preview_white"),
            ("black", "preview_black"),
        ]
        self._open_choice_menu(
            self.preview_button,
            self.t("preview_background"),
            [
                (
                    self.t(key),
                    self.preview_background == value,
                    lambda v=value: self.set_preview_background(v),
                )
                for value, key in labels
            ],
            210,
        )

    def set_preview_background(self, value):
        if value not in ("transparent", "white", "black"):
            return
        self.preview_background = value
        self.viewer.set_background(value)
        self.dismiss_choice_popup()
        self.persist()
        self.update_controls()

    def change_theme(self, value):
        self.dismiss_choice_popup()
        super().change_theme(value)

    def change_language(self, value):
        self.dismiss_choice_popup()
        super().change_language(value)

    def switch_task(self, task):
        if self.busy or self.modal is not None or task == self.task:
            return
        self.dismiss_choice_popup()
        self.dismiss_jpg_palette()

        # Save the branch we are leaving.
        self.sync_document()
        self.dismiss_popup()

        # Switching modes only changes workspace. Each mode keeps its own input
        # and result, so two independent results can coexist and remain savable.
        self.task = task
        self.source = self.task_sources.get(task)
        self.result = self.results.get(task)

        self.viewer.zoom_enabled = False
        self.viewer.view_mode = "compare"
        self.viewer.compare = True
        # White/black are inspection backdrops for Remove BG only; they never
        # become image pixels. Upscale must always show transferred alpha on
        # the checkerboard so a transparent result cannot look flattened.
        self.viewer.set_background(
            self.preview_background if task == "remove" else "transparent"
        )
        from lena_native import atomic_redraw

        with atomic_redraw(self.side, self.controls):
            self.viewer.set_images(self.source, self.result, reset=True)
            self.status("")
            self.update_controls()

    def send_result(self):
        if self.busy or self.result is None:
            return

        target = "remove" if self.task == "upscale" else "upscale"
        self.sync_document()

        lineage = self.result_lineage.get(self.task, frozenset())

        # Block either:
        # 1) a process already present in this image's lineage, or
        # 2) forwarding this exact result down the same branch a second time.
        if target in lineage or self.result_forwarded.get(self.task, False):
            return

        transferred = self.result

        # Mark THIS source result as already forwarded. Switching back to this
        # workspace will therefore not offer the same transfer again.
        self.result_forwarded[self.task] = True

        # Keep the source branch/result intact. The target workspace receives
        # this result as a fresh input. Any previous target result is replaced
        # only in the target workspace; the source result remains available.
        self.task_sources[target] = transferred
        self.input_lineage[target] = frozenset(lineage)
        self.results[target] = None
        self.result_lineage[target] = frozenset()
        self.result_forwarded[target] = False

        self.switch_task(target)

    def sync_document(self):
        current_source = self.task_sources.get(self.task)

        # If source changed outside pipeline navigation/transfer (Choose Photo,
        # drag/drop, paste, clear), it is a genuinely new document. Start both
        # workspaces from that same original source and clear the old branches.
        if self.source is not current_source:
            new_source = self.source
            self.document_source = new_source
            self.task_sources = {"remove": new_source, "upscale": new_source}
            self.input_lineage = {"remove": frozenset(), "upscale": frozenset()}
            self.results = {"remove": None, "upscale": None}
            self.result_lineage = {"remove": frozenset(), "upscale": frozenset()}
            self.result_forwarded = {"remove": False, "upscale": False}
            self.validation_warnings = {"remove": False, "upscale": False}
            current_source = new_source

        # Keep the active workspace state synchronized. A newly produced result
        # inherits its input history and adds the process that just ran.
        previous = self.results.get(self.task)
        if self.result is not None and self.result is not previous:
            self.result_lineage[self.task] = frozenset(
                set(self.input_lineage.get(self.task, frozenset())) | {self.task}
            )
            self.result_forwarded[self.task] = False
        elif self.result is None:
            self.result_lineage[self.task] = frozenset()
            self.result_forwarded[self.task] = False

        self.task_sources[self.task] = self.source
        self.results[self.task] = self.result

    def apply_theme(self):
        if getattr(self, "jpg_palette", None):
            self.dismiss_jpg_palette()
        super().apply_theme()
        if self.enhanced_ready:
            # Child canvases inherit the rail color via the segmented control's
            # cget; exposed pixels at its outer edges must match the footer.
            for control in (self.language, self.theme):
                for segment in control._buttons_dict.values():
                    segment.configure(bg_color="#121316" if self.dark else "#F5F5F7")
            footer = "#25262A" if self.dark else "#D8D4DC"
            base = "#121316" if self.dark else "#F5F5F7"
            ink = "#FFFFFF" if self.dark else "#24212B"
            subtle = "#35373F" if self.dark else "#D2CDD6"
            hover = "#484A54" if self.dark else "#C2BBC6"
            for button in (
                self.donation,
                self.settings_button,
                self.guide_button,
                self.preferences_button,
            ):
                button.configure(
                    fg_color=subtle, bg_color=base, text_color=ink, hover_color=hover
                )
            self.settings_button.configure(image=self.icon("settings", 16))
            self.guide_button.configure(image=self.icon("guide", 16))
            self.preview_button.configure(
                fg_color=footer,
                bg_color=base,
                text_color=ink,
                hover_color="#3A3B42" if self.dark else "#C0BAC5",
            )
            self.preferences_button.configure(text="🌐  │  ☀")
            self.result_warning.configure(
                fg_color="#302936" if self.dark else "#F2E7F4", border_color="#8D6A98"
            )
            self.result_warning_label.configure(text_color=ink)
            header_bg = "#191A1F" if self.dark else "#F5F5F7"
            self.models_button.configure(
                fg_color=subtle, bg_color=header_bg, text_color=ink, hover_color=hover
            )
            for button in (self.save_button, self.jpg_button):
                button.configure(
                    fg_color="#117AD3",
                    bg_color=header_bg,
                    text_color="#FFFFFF",
                    hover_color="#268CE6",
                )
            self.mode_switch.set_background(header_bg)
            self.update_controls()

    def status(self, text):
        super().status(text)
        if self.enhanced_ready:
            if text:
                self.message.grid()
            else:
                self.message.grid_remove()

    def update_controls(self):
        self.sync_document()
        super().update_controls()
        if not self.enhanced_ready:
            return
        up = self.task == "upscale"
        self.viewer.zoom_enabled = False
        self.viewer.navigation_locked = self.busy
        active = "#F4F0F6" if self.dark else "#24212B"
        inactive = "#94909C" if self.dark else "#3F3943"
        self.remove_label.configure(
            text="Hapus Latar" if self.lang == "id" else "Remove BG",
            text_color=inactive if up else active,
        )
        self.up_label.configure(text="Upscale", text_color=active if up else inactive)
        if self.busy:
            self.progress.grid()
        else:
            self.progress.grid_remove()
        self.jpg_button.configure(
            state="normal" if self.result is not None and not self.busy else "disabled"
        )
        if self.jpg_palette is not None and (self.result is None or self.busy):
            self.dismiss_jpg_palette()
        self.models_button.configure(text="SPAN" if up else "AI Model")
        self._header_task = self.task
        target = "remove" if self.task == "upscale" else "upscale"
        current_ready = self.result is not None and not self.busy
        lineage = self.result_lineage.get(self.task, frozenset())
        already_processed = target in lineage
        already_forwarded = self.result_forwarded.get(self.task, False)
        transfer_ready = (
            current_ready and not already_processed and not already_forwarded
        )

        if self.busy:
            transfer_note = self.t("busy")
        elif current_ready and already_forwarded:
            transfer_note = self.words(
                "Hasil ini sudah diteruskan ke proses berikutnya.",
                "This result was already sent to the next process.",
            )
        elif current_ready and already_processed:
            if target == "remove":
                transfer_note = self.words(
                    "Gambar ini sudah melalui Hapus Background.",
                    "This image already went through Remove Background.",
                )
            else:
                transfer_note = self.words(
                    "Gambar ini sudah melalui Upscale.",
                    "This image already went through Upscale.",
                )
        elif current_ready:
            transfer_note = ""
        else:
            transfer_note = self.words(
                "Proses foto terlebih dahulu\nuntuk memakai fitur ini.",
                "Process the photo first\nto use this feature.",
            )

        self.transfer_hint.configure(
            text=transfer_note, text_color="#A6A1AA" if self.dark else "#343039"
        )
        if self.busy:
            self.info_bar.pack(fill="x", padx=12, pady=(5, 0), before=self.viewer)
        else:
            self.info_bar.pack_forget()
        preview_ready = not up and self.result is not None and not self.busy
        if preview_ready:
            label = {
                "transparent": self.t("preview_transparent"),
                "white": self.t("preview_white"),
                "black": self.t("preview_black"),
            }[self.preview_background]
            self._fit_preview_button(f'{self.t("preview_background")}: {label}  ▾')
        elif self.choice_trigger is self.preview_button:
            self.dismiss_choice_popup()
        self._layout_transfer_footer()
        warning_ready = preview_ready and self.validation_warnings.get("remove", False)
        if warning_ready:
            self.result_warning_label.configure(text=self.t("result_incomplete"))
            self.try_best_button.configure(text=self.t("try_best"))
            self.result_warning.place(relx=0.5, rely=1, y=-14, anchor="s")
            self.result_warning.lift()
        else:
            self.result_warning.place_forget()

        state = (
            self.task,
            self.lang,
            self.dark,
            transfer_ready,
            already_processed,
            already_forwarded,
            self.side.winfo_width(),
        )
        if self._transfer_key != state:
            self._transfer_key = state
            art = transfer_art(self.task, self.lang, self.dark).copy()
            f = max(
                0.5, self.side.winfo_width() / 443 / self.sidebar._get_widget_scaling()
            )
            height = 60.5 * f
            width = height * art.width / art.height
            if not transfer_ready:
                art.putalpha(art.getchannel("A").point(lambda a: round(a * 0.4)))
            self.transfer._art_frames = None
            base = "#121316" if self.dark else "#F5F5F7"
            self.transfer.configure(
                image=ctk.CTkImage(art, size=(width, height)),
                width=width,
                height=height,
                corner_radius=0,
                border_spacing=0,
                fg_color=base,
                bg_color=base,
                state="normal" if transfer_ready else "disabled",
            )
        self.refresh_manager()

    def try_best_quality(self):
        if self.busy or self.task != "remove" or self.source is None:
            return
        if path("mvanet") is None:
            self.download_models(["mvanet"])
            return
        self.pick_quality("mvanet")
        self.infer("mvanet")

    def set_scale(self, value):
        if not self.busy:
            self.scale = int(str(value)[0])
            self.draw_sidebar()

    def start(self):
        self.dismiss_jpg_palette()
        if self.task == "remove":
            return super().start()
        if self.busy:
            self.cancel.set()
            return
        if self.source is None:
            self.choose_photo()
            return
        try:
            output_size(self.source, self.scale)
        except ValueError:
            messagebox.showinfo("Upscale", self.t("output_limit"), parent=self)
            return
        missing = path(MODEL) is None
        if not self.begin():
            return
        if missing:
            self.download_active = True
            self.loading_logo.stop()
        # Busy state prevents replacing/editing the input; the worker only reads it.
        photo = self.source
        scale = self.scale
        mode = self.mode
        devices = list(self.devices)

        def work():
            try:
                if missing:
                    self.report("model_label", ("SPAN", 1, 1))
                    prepare(MODEL, self.report, self.cancel)
                    if self.cancel.is_set():
                        raise Cancelled()
                    self.report("upscale_downloaded", None)
                from lena_worker import process

                output, backend, fallback = process(
                    photo, MODEL, mode, devices, self.report, self.cancel, scale=scale
                )
                self.report("result", (output, backend, fallback))
            except Cancelled:
                self.report("cancelled", None)
            except Exception as error:
                self.report("error", str(error))

        threading.Thread(target=work, daemon=True).start()

    def report(self, kind, value):
        if kind == "stage" and value.startswith("upscale:"):
            _, done, total = value.split(":")
            return super().report("tile_progress", (int(done), int(total)))
        super().report(kind, value)

    def _result_has_transparency(self):
        if self.result is None or "A" not in self.result.getbands():
            return False
        try:
            return self.result.getchannel("A").getextrema()[0] < 255
        except (ValueError, IndexError):
            return False

    def dismiss_jpg_palette(self):
        panel = getattr(self, "jpg_palette", None)
        self.jpg_palette = None
        if panel is not None:
            try:
                panel.destroy()
            except tk.TclError:
                pass

    def dismiss_quality_outside(self, event):
        panel = getattr(self, "choice_popup", None)
        if panel is not None:
            widget = event.widget
            while widget is not None:
                if widget is panel or widget is self.choice_trigger:
                    return
                widget = getattr(widget, "master", None)
            self.dismiss_choice_popup()
        panel = getattr(self, "jpg_palette", None)
        if panel is not None:
            widget = event.widget
            while widget is not None:
                if widget is panel or widget is getattr(self, "jpg_button", None):
                    return
                widget = getattr(widget, "master", None)
            self.dismiss_jpg_palette()
            return
        return super().dismiss_quality_outside(event)

    def escape(self, event=None):
        if getattr(self, "choice_popup", None) is not None:
            self.dismiss_choice_popup()
            return "break"
        if getattr(self, "jpg_palette", None) is not None:
            self.dismiss_jpg_palette()
            return "break"
        return super().escape(event)

    def save_jpg(self):
        if self.busy or self.result is None:
            return
        if not self._result_has_transparency():
            self.dismiss_jpg_palette()
            self.export_jpg("#FFFFFF")
            return
        if self.jpg_palette is not None:
            self.dismiss_jpg_palette()
            return
        self.show_jpg_palette()

    def show_jpg_palette(self):
        if self.result is None:
            return
        self.dismiss_popup()
        self.update_idletasks()

        # Compact embedded chooser: the Illustrator mockup is ~2.19:1.
        # Use the workspace as parent so CTk's rounded-corner background
        # matches the surface underneath instead of exposing a dark rectangle.
        scale = self.workspace._get_widget_scaling()
        available = max(1, self.workspace.winfo_width() / scale - 28)
        f = max(0.78, min(1.0, available / 540))
        width = 540 * f
        height = 247 * f

        workspace_bg = self.workspace.cget("fg_color")
        panel = ctk.CTkFrame(
            self.workspace,
            width=width,
            height=height,
            fg_color="#282B31" if self.dark else "#F3F1F4",
            bg_color=workspace_bg,
            border_width=1,
            border_color="#69636D" if self.dark else "#B9B4BF",
            corner_radius=18 * f,
        )
        panel.pack_propagate(False)
        self.jpg_palette = panel

        ink = "#F8F7F9" if self.dark else "#202128"
        accent = "#3194F7"
        title = self.words(
            "JPG tidak mendukung transparansi", "JPG has no transparency"
        )
        subtitle = self.words(
            "Pilih warna latar untuk area transparan:",
            "Choose a background color for the transparent areas:",
        )
        png_text = self.words("Simpan ke PNG saja?", "Save to PNG instead?")

        ctk.CTkLabel(
            panel,
            text=title,
            text_color=ink,
            font=("Zalando Sans Expanded SemiBold", max(15, round(19 * f))),
            height=0,
        ).place(relx=0.5, y=24 * f, anchor="n")

        ctk.CTkLabel(
            panel,
            text=subtitle,
            text_color=ink,
            font=("Red Hat Display SemiBold", max(12, round(15 * f))),
            height=0,
        ).place(relx=0.5, y=61 * f, anchor="n")

        colors = [
            ("#FFFFFF", 62),
            ("#000000", 139),
            ("#808080", 216),
            ("#0090FF", 340),
            ("#DB1514", 418),
        ]
        sw = 61 * f
        for color, x in colors:
            button = ctk.CTkButton(
                panel,
                text="",
                width=sw,
                height=sw,
                corner_radius=7 * f,
                fg_color=color,
                hover_color=color,
                border_width=max(1, round(2 * f)),
                border_color="#FFFFFF",
                command=lambda c=color: self._choose_jpg_background(c),
            )
            try:
                button.configure(cursor="hand2")
            except (tk.TclError, ValueError):
                pass
            button.place(x=x * f, y=106 * f)

        ctk.CTkFrame(
            panel,
            width=max(1, round(2 * f)),
            height=61 * f,
            fg_color="#F3F3F3",
            corner_radius=0,
        ).place(x=308 * f, y=106 * f)

        link = ctk.CTkLabel(
            panel,
            text=png_text,
            text_color=accent,
            cursor="hand2",
            font=ctk.CTkFont(
                "Red Hat Display ExtraBold", max(13, round(16 * f)), underline=True
            ),
            height=0,
        )
        link.place(relx=0.5, y=199 * f, anchor="n")
        link.bind("<Button-1>", lambda e: self._save_png_from_jpg_palette())

        # The panel has never been mapped while its children are being built.
        # One layout flush, then one final placement = no placeholder flash and
        # no artificial entrance delay.
        panel.update_idletasks()
        center = (
            self.save_group.winfo_rootx()
            - self.workspace.winfo_rootx()
            + self.save_group.winfo_width() / 2
        ) / scale
        center = max(
            width / 2 + 8,
            min(self.workspace.winfo_width() / scale - width / 2 - 8, center),
        )
        panel.place(x=center, y=14, anchor="n")
        panel.lift()

    def _choose_jpg_background(self, color):
        self.dismiss_jpg_palette()
        self.export_jpg(color)

    def _save_png_from_jpg_palette(self):
        self.dismiss_jpg_palette()
        self.save()

    def export_jpg(self, background):
        suffix = f"-LENA-{self.scale}x.jpg" if self.task == "upscale" else "-LENA.jpg"
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Save JPG",
            initialfile=f"{self.source_name}{suffix}",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg")],
        )
        if not filename:
            return
        try:
            jpeg_image(self.result, background).save(
                filename, "JPEG", quality=95, subsampling=0
            )
            self.status(self.t("saved_jpg"))
        except OSError:
            messagebox.showerror(
                self.t("error_title"), self.t("save_error"), parent=self
            )
