from lena_platform import open_local

"""September Illustrator panels, with live model data and localized copy."""
import os
import ctypes
import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk
from lena_panels import Panels
from lena_models import QUALITIES, REFINER, MODELS, path, size, size_text
from lena_config import ROOT
from lena_native import rounded_widget


class RedesignedPanels(Panels):
    def words(self, ind, eng):
        return ind if self.lang == "id" else eng

    @property
    def panel_color(self):
        return "#282C32" if self.dark else "#F5F3F5"

    @property
    def card_color(self):
        return "#363A40" if self.dark else "#DDDCE2"

    @property
    def ink(self):
        return "#FCFAFC" if self.dark else "#202128"

    @property
    def muted(self):
        return "#B9B5BE" if self.dark else "#4C4851"

    def label(self, parent, text, fs=14, weight="Regular", **kw):
        return ctk.CTkLabel(
            parent,
            text=text,
            font=("Red Hat Display " + weight, fs),
            text_color=self.ink,
            height=0,
            **kw,
        )

    def rule(self, parent, strong=False, pady=12):
        ctk.CTkFrame(
            parent,
            height=2,
            corner_radius=0,
            fg_color=self.ink if strong else self.muted,
        ).pack(fill="x", pady=pady)

    def outline_button(self, parent, text, command, **kw):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=43,
            font=("Red Hat Display SemiBold", 13),
            fg_color=self.panel_color,
            text_color=self.ink,
            hover_color=self.card_color,
            border_width=1,
            border_color="#74747C" if self.dark else "#918C98",
            corner_radius=7,
            **kw,
        )

    def paragraph(self, body, text, font=14):
        label = self.label(body, text, font, anchor="w", justify="left", wraplength=360)
        label.pack(fill="x", pady=7)
        body.bind(
            "<Configure>",
            lambda e: label.configure(
                wraplength=max(100, e.width / body._get_widget_scaling() - 4)
            ),
            add="+",
        )
        return label

    def heading(self, body, text):
        self.label(body, text, 25, "Light", anchor="w").pack(fill="x", pady=(0, 4))
        self.rule(body, True, (10, 16))

    def dialog(self, title, width=430, height=548):
        # Custom Illustrator-style dialogs.
        #
        # Window lifecycle on Windows:
        # - Buy Me A Coffee is disposable: Alt+Tab destroys it cleanly.
        # - Settings / Guide are persistent non-modal dialogs: they keep their
        #   Tk objects across Alt+Tab and are restored when LENA becomes active.
        # - Other dialogs (onboarding, etc.) keep the traditional modal grab.
        #
        # Never combine overrideredirect + delayed grab_set with a window that
        # may be unmapped by Windows during Alt+Tab; that is the freeze source.
        self.dismiss_popup()
        support_popup = title == "Buy me a coffee"
        persistent_kind = (
            "settings"
            if title == self.t("settings")
            else (
                "guide"
                if title == self.t("guide")
                else (
                    "language"
                    if title == "Choose your language"
                    else "welcome" if title == "LENA" else None
                )
            )
        )
        persistent_popup = persistent_kind is not None
        requested_kind = "support" if support_popup else persistent_kind

        if self.modal is not None:
            existing = self.modal
            existing_kind = getattr(existing, "_lena_kind", None)
            if (
                persistent_popup
                and existing_kind == persistent_kind
                and getattr(existing, "_lena_persistent", False)
            ):
                # Re-open means RESTORE, never repopulate the existing body.
                try:
                    restore = getattr(existing, "_lena_restore", None)
                    if restore:
                        restore()
                    else:
                        existing.deiconify()
                        existing.lift()
                        existing.focus_set()
                except tk.TclError:
                    pass
                existing._lena_reused = True
                return existing, existing.body, existing.close_panel

            if support_popup or persistent_popup:
                # Switching between Settings <-> Guide, or opening Coffee while
                # another custom dialog exists, must fully retire the old pair
                # before constructing the new one. Never let an animated stale
                # close finish after self.modal already points at a new window.
                destroy_now = getattr(existing, "_lena_destroy_now", None)
                if destroy_now:
                    try:
                        destroy_now(False)
                    except (tk.TclError, TypeError):
                        pass
                else:
                    try:
                        existing.destroy()
                    except tk.TclError:
                        pass
                    if self.modal is existing:
                        self.modal = None
            else:
                try:
                    existing.deiconify()
                    existing.lift()
                    existing.focus_set()
                except tk.TclError:
                    pass
                return existing, existing.body, existing.close_panel

        self.update_idletasks()

        shade = tk.Toplevel(self)
        shade.withdraw()
        shade.overrideredirect(True)
        shade.configure(bg="#080A0E")
        shade.attributes("-alpha", 0.70)
        shade.transient(self)

        win = ctk.CTkToplevel(self)
        win.withdraw()
        win.title(title)
        win.overrideredirect(True)
        win.transient(self)
        win.configure(fg_color="#010203" if os.name == "nt" else self.panel_color)
        win._lena_shade = shade
        win._lena_persistent = persistent_popup
        win._lena_kind = requested_kind
        win._lena_reused = False
        win._lena_content_built = False
        win._lena_root_bindings = []
        win._lena_closing = False
        win._lena_watch_job = None

        # Keep helper windows out of the Windows taskbar / Alt+Tab list.
        if os.name == "nt":
            try:
                shade.attributes("-toolwindow", True)
            except tk.TclError:
                pass
            try:
                win.attributes("-toolwindow", True)
            except tk.TclError:
                pass
            try:
                win.attributes("-transparentcolor", "#010203")
            except tk.TclError:
                pass

        def sync_shade():
            try:
                if shade.winfo_exists():
                    shade.geometry(
                        f"{self.winfo_width()}x{self.winfo_height()}+"
                        f"{self.winfo_rootx()}+{self.winfo_rooty()}"
                    )
            except tk.TclError:
                pass

        sync_shade()

        scale = win._get_window_scaling()
        screen_w = (
            ctypes.windll.user32.GetSystemMetrics(0)
            if os.name == "nt"
            else self.winfo_screenwidth()
        )
        screen_h = (
            ctypes.windll.user32.GetSystemMetrics(1)
            if os.name == "nt"
            else self.winfo_screenheight()
        )
        width = min(width, (screen_w - 40) / scale)
        height = min(height, (screen_h - 90) / scale)
        x = max(0, self.winfo_rootx() + (self.winfo_width() - width * scale) / 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - height * scale) / 2)
        target_w, target_h, target_x, target_y = (
            round(width),
            round(height),
            round(x),
            round(y),
        )
        win.geometry(f"{target_w}x{target_h}+{target_x}+{target_y}")
        win._lena_target_geometry = (target_w, target_h, target_x, target_y)

        self.modal = win
        win._modal_jobs = []

        def cancel_modal_jobs():
            for job in list(getattr(win, "_modal_jobs", [])):
                try:
                    win.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
            win._modal_jobs = []
            watch = getattr(win, "_lena_watch_job", None)
            if watch is not None:
                try:
                    win.after_cancel(watch)
                except (tk.TclError, ValueError):
                    pass
                win._lena_watch_job = None

        def clear_root_bindings():
            for sequence, binding in list(getattr(win, "_lena_root_bindings", [])):
                try:
                    self.unbind(sequence, binding)
                except (tk.TclError, TypeError):
                    pass
            win._lena_root_bindings = []

        def closed(restore_focus=True):
            # Destroy this exact native pair even if another dialog has already
            # become self.modal. Only clear the shared pointer when it is ours.
            if self.modal is win:
                self.modal = None
            cancel_modal_jobs()
            clear_root_bindings()

            # Defensive cleanup only. Persistent dialogs never create a grab,
            # but onboarding/other modal dialogs still can.
            try:
                grabber = win.grab_current()
                if grabber is not None and grabber.winfo_toplevel() is win:
                    grabber.grab_release()
            except tk.TclError:
                pass

            try:
                win.destroy()
            except tk.TclError:
                pass
            try:
                shade.destroy()
            except tk.TclError:
                pass

            if restore_focus:
                try:
                    self.focus_set()
                except tk.TclError:
                    pass

        win.close_panel = closed
        win._lena_destroy_now = closed
        win.protocol("WM_DELETE_WINDOW", lambda: win.close_panel())
        win.bind("<Escape>", lambda e: (win.close_panel(), "break")[1])

        shell = ctk.CTkFrame(
            win,
            fg_color=self.panel_color,
            border_width=1,
            border_color="#77717C" if self.dark else "#BAB5C0",
            corner_radius=13,
        )
        shell.pack(fill="both", expand=True)
        win._lena_shell = shell

        close = tk.Canvas(
            shell,
            width=round(24 * scale),
            height=round(24 * scale),
            bg=self.panel_color,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=True,
        )
        for coords in [(8, 8, 16, 16), (16, 8, 8, 16)]:
            close.create_line(
                *(round(v * scale) for v in coords),
                fill=self.muted,
                width=max(1, round(scale)),
            )
        close.bind("<Button-1>", lambda e: win.close_panel())
        close.bind("<Return>", lambda e: win.close_panel())
        close.bind("<space>", lambda e: win.close_panel())
        close.bind("<Enter>", lambda e: close.configure(bg=self.card_color))
        close.bind("<Leave>", lambda e: close.configure(bg=self.panel_color))
        close.place(relx=1, x=-round(7 * scale), y=round(5 * scale), anchor="ne")

        body = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=self.panel_color,
            scrollbar_button_hover_color=self.muted,
        )
        body.pack(fill="both", expand=True, padx=(24, 16), pady=(25, 20))
        win.body = body
        close.tk.call("raise", close._w)
        win.close_button = close

        # The shade provides modal-looking UX without a Tk input grab.
        def raise_dialog(event=None):
            try:
                if self.modal is not win or not win.winfo_exists():
                    return
                sync_shade()
                shade.deiconify()
                shade.lift()
                win.deiconify()
                win.lift()
                win.focus_set()
            except tk.TclError:
                pass

        shade.bind("<Button-1>", raise_dialog)

        if support_popup:
            # donate() owns the visible fade/slide. Only reveal the shade once
            # its content has been built.
            def reveal_support_shade():
                if self.modal is not win or not shade.winfo_exists():
                    return
                try:
                    sync_shade()
                    shade.deiconify()
                    shade.lift()
                    win.lift()
                except tk.TclError:
                    pass

            shade.after_idle(reveal_support_shade)

            # Disposable behavior: external focus destroys this pair so no
            # stale native toolwindow survives.
            def check_external_focus(event=None):
                def check():
                    if self.modal is not win or not win.winfo_exists():
                        return
                    try:
                        focused = self.focus_get()
                    except tk.TclError:
                        focused = None
                    if focused is None:
                        closed(False)

                try:
                    win.after(80, check)
                except tk.TclError:
                    pass

            focus_binding = self.bind("<FocusOut>", check_external_focus, add="+")
            win._lena_root_bindings.append(("<FocusOut>", focus_binding))

            original_closed = win.close_panel

            def support_closed(restore_focus=True):
                original_closed(restore_focus)

            win.close_panel = support_closed
            win.protocol("WM_DELETE_WINDOW", lambda: win.close_panel())
            win.bind("<Escape>", lambda e: win.close_panel())

        elif persistent_popup:
            # Settings / Guide: persistent, visually modal, but NEVER a Tk grab.
            # Build hidden, reveal smoothly, then watch application activation
            # so Alt+Tab restores this exact window instead of recreating it.
            try:
                win.attributes("-alpha", 0)
            except tk.TclError:
                pass

            offset = 18
            size = f"{target_w}x{target_h}"
            win.geometry(f"{size}+{target_x}+{target_y+offset}")

            def restore_persistent():
                if self.modal is not win or not win.winfo_exists():
                    return
                try:
                    # Re-assert transient ownership before every restore. Tk/
                    # Windows can lose the effective owner relationship for an
                    # overrideredirect toolwindow across repeated Alt+Tab cycles.
                    shade.transient(self)
                    win.transient(self)
                    sync_shade()
                    shade.deiconify()
                    shade.lift()
                    win.deiconify()
                    win.lift()
                    win.after(20, lambda: win.lift() if win.winfo_exists() else None)
                    win.after(
                        25, lambda: win.focus_set() if win.winfo_exists() else None
                    )
                except tk.TclError:
                    pass

            win._lena_restore = restore_persistent

            def slide_in(step=0, total=8):
                if self.modal is not win or not win.winfo_exists():
                    return
                if step > total:
                    try:
                        win.geometry(f"{size}+{target_x}+{target_y}")
                        win.attributes("-alpha", 1)
                    except tk.TclError:
                        pass
                    return
                t = step / total
                eased = 1 - (1 - t) ** 3
                try:
                    win.attributes("-alpha", eased)
                    win.geometry(
                        f"{size}+{target_x}+{round(target_y+offset*(1-eased))}"
                    )
                except tk.TclError:
                    return
                win.after(12, lambda: slide_in(step + 1, total))

            def reveal_persistent():
                if self.modal is not win or not win.winfo_exists():
                    return
                try:
                    win.update_idletasks()
                    sync_shade()
                    shade.deiconify()
                    shade.lift()
                    win.deiconify()
                    win.lift()
                except tk.TclError:
                    return
                win.after(1, slide_in)

            win.after_idle(reveal_persistent)

            # Persistent dialogs must never become orphan toolwindows over an
            # unrelated application. On Windows, use the actual foreground
            # process rather than Tk focus events (which are timing-sensitive
            # with overrideredirect windows). When LENA loses foreground, keep
            # the dialog objects/state but temporarily unmap both native windows;
            # when LENA becomes foreground again, restore the SAME pair.
            win._lena_external_hidden = False

            if os.name == "nt":
                user32 = ctypes.windll.user32
                current_pid = os.getpid()

                def lena_is_foreground():
                    try:
                        hwnd = user32.GetForegroundWindow()
                        if not hwnd:
                            return False
                        pid = ctypes.c_ulong(0)
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        return pid.value == current_pid
                    except Exception:
                        return self.focus_displayof() is not None

            else:

                def lena_is_foreground():
                    try:
                        return self.focus_displayof() is not None
                    except tk.TclError:
                        return False

            def hide_persistent_external():
                if self.modal is not win or not win.winfo_exists():
                    return
                if getattr(win, "_lena_external_hidden", False):
                    return
                win._lena_external_hidden = True
                try:
                    win.withdraw()
                except tk.TclError:
                    pass
                try:
                    shade.withdraw()
                except tk.TclError:
                    pass

            def restore_persistent_external():
                if self.modal is not win or not win.winfo_exists():
                    return
                if not getattr(win, "_lena_external_hidden", False):
                    return
                win._lena_external_hidden = False
                restore_persistent()

            def activation_watch():
                if self.modal is not win or not win.winfo_exists():
                    return
                try:
                    root_state = self.state()
                except tk.TclError:
                    root_state = "withdrawn"
                active = lena_is_foreground() and root_state not in (
                    "iconic",
                    "withdrawn",
                )
                if active:
                    restore_persistent_external()
                else:
                    hide_persistent_external()
                try:
                    win._lena_watch_job = win.after(60, activation_watch)
                except tk.TclError:
                    win._lena_watch_job = None

            win._lena_watch_job = win.after(60, activation_watch)

            # Escape must work even if Windows gives focus back to the main LENA
            # window before the persistent dialog has reclaimed keyboard focus.
            root_escape = self.bind(
                "<Escape>", lambda e: (win.close_panel(), "break")[1], add="+"
            )
            win._lena_root_bindings.append(("<Escape>", root_escape))

            base_closed = win.close_panel

            def persistent_close(restore_focus=True):
                if getattr(win, "_lena_closing", False):
                    return
                win._lena_closing = True

                def fade(step=8):
                    if not win.winfo_exists():
                        return
                    if step <= 0:
                        base_closed(restore_focus)
                        return
                    amount = step / 8
                    try:
                        win.attributes("-alpha", amount)
                        win.geometry(
                            f"{size}+{target_x}+{round(target_y+offset*(1-amount))}"
                        )
                    except tk.TclError:
                        base_closed(restore_focus)
                        return
                    win.after(10, lambda: fade(step - 1))

                fade()

            win.close_panel = persistent_close
            win.protocol("WM_DELETE_WINDOW", lambda: win.close_panel())
            win.bind("<Escape>", lambda e: (win.close_panel(), "break")[1])

        else:
            # Onboarding / other true modal dialogs keep the old behavior.
            def reveal_modal():
                if self.modal is not win or not win.winfo_exists():
                    return
                try:
                    win.update_idletasks()
                    win.attributes("-alpha", 1)
                    sync_shade()
                    shade.deiconify()
                    shade.lift()
                    win.deiconify()
                    win.lift()
                    win.grab_set()
                    win.focus_set()
                except tk.TclError:
                    return

            win.after_idle(reveal_modal)

        if hasattr(self, "wheel_router"):
            self.wheel_router.walk(win)
        return win, body, closed

    def open_settings(self):
        win, body, closed = self.dialog(self.t("settings"), 430, 548)
        if getattr(win, "_lena_content_built", False):
            return
        win._lena_content_built = True
        self.heading(body, self.t("settings"))
        self.label(
            body,
            self.words("Mode Pemrosesan:", "Processing Mode:"),
            17,
            "SemiBold",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        self.radio_mode = tk.StringVar(value=self.mode)

        def change():
            self.mode = self.radio_mode.get()
            self.persist()

        for value, text in [
            (
                "auto",
                self.words("Auto - GPU jika tersedia", "Auto - GPU when available"),
            ),
            ("cpu", self.words("CPU saja", "CPU only")),
        ]:
            ctk.CTkRadioButton(
                body,
                text=text,
                variable=self.radio_mode,
                value=value,
                command=change,
                font=("Red Hat Display Light", 17),
                text_color=self.ink,
                fg_color="#3294F5",
                border_color="#74717A",
                radiobutton_width=22,
                radiobutton_height=22,
                state="disabled" if self.busy else "normal",
            ).pack(anchor="w", pady=6)
        self.paragraph(
            body,
            self.words(
                "Auto memakai GPU saat model mendukungnya, dan otomatis beralih ke CPU jika GPU pernah gagal.",
                "Auto uses your GPU when a model supports it, and switches to CPU automatically if the GPU has failed before.",
            ),
        )
        self.paragraph(
            body,
            self.words("GPU Terdeteksi: ", "GPU Detected: ")
            + (", ".join(d["name"] for d in self.devices) or self.t("no_gpu")),
        )
        self.rule(body, pady=(14, 18))
        self.outline_button(
            body,
            self.words("Buka Folder Model", "Open Models Folder"),
            self.open_cache,
            width=143,
        ).pack(anchor="w")
        self.rule(body, pady=(18, 16))
        self.label(
            body, "LENA 1.0 by Hiratsani © 2026", 14, "SemiBold", anchor="w"
        ).pack(fill="x")
        self.paragraph(body, self.t("offline"), 14)
        footer_actions = ctk.CTkFrame(body, fg_color="transparent")
        footer_actions.pack(anchor="w", pady=(3, 0))
        button_width = 105
        self.outline_button(
            footer_actions,
            self.words("Lisensi", "Licenses"),
            lambda: open_local(ROOT / "THIRD-PARTY-NOTICES.txt"),
            width=button_width,
        ).pack(side="left", padx=(0, 8))
        self.outline_button(
            footer_actions, "Welcome", self.replay_welcome, width=button_width
        ).pack(side="left")

    def open_guide(self):
        win, body, closed = self.dialog(self.t("guide"), 405, 552)
        if getattr(win, "_lena_content_built", False):
            return
        win._lena_content_built = True
        for title, key in [
            (self.t("remove_tab"), "steps"),
            (self.words("Perbesar Gambar", "Image Upscale"), "upscale_steps"),
        ]:
            ctk.CTkLabel(
                body,
                text=title,
                font=("Zalando Sans Expanded Medium", 22),
                text_color=self.ink,
                height=0,
                anchor="w",
            ).pack(fill="x", pady=(0 if key == "steps" else 14, 0))
            self.rule(body, True, (10, 8))
            for n, step in enumerate(self.t(key).split("\n\n"), 1):
                row = ctk.CTkFrame(body, fg_color="transparent")
                row.pack(fill="x", pady=3)
                self.label(
                    row, str(n) + ".", 13, "SemiBold", width=22, anchor="nw"
                ).pack(side="left", anchor="n")
                label = self.label(
                    row,
                    step.partition(". ")[2] or step,
                    13,
                    "Light",
                    anchor="w",
                    justify="left",
                    wraplength=306,
                )
                label.pack(side="left", fill="x", expand=True)
                row.bind(
                    "<Configure>",
                    lambda e, l=label: l.configure(
                        wraplength=max(100, e.width / body._get_widget_scaling() - 26)
                    ),
                    add="+",
                )
        self.paragraph(body, self.t("transfer_guide"), 13)
        self.paragraph(
            body,
            self.words(
                "Foto tidak pernah meninggalkan perangkatmu. Internet hanya diperlukan untuk download model tambahan.",
                "Photos never leave your device. Internet is only needed to download optional models.",
            ),
            13,
        )

    def language_dialog(self, replay=False):
        # Compact, Alt+Tab-safe onboarding chooser.
        win, body, closed = self.dialog("Choose your language", 360, 148)
        if getattr(win, "_lena_content_built", False):
            return
        win._lena_content_built = True

        # No close button for this step. Skip is the dim area outside or Escape.
        try:
            close = getattr(win, "close_button", None)
            if close is not None:
                close.place_forget()
        except tk.TclError:
            pass

        # CTkScrollableFrame was clipping the greeting line at this very small
        # dialog height. Hide it completely and build directly on the dialog
        # shell, then place ONE fixed composition at the exact visual center.
        # A CTkScrollableFrame's master is its internal canvas, not the
        # visible dialog shell. pack_forget() hides that whole scroll wrapper.
        shell = win._lena_shell
        try:
            body.pack_forget()
        except tk.TclError:
            pass

        content = ctk.CTkFrame(shell, width=334, height=108, fg_color="transparent")
        content.pack_propagate(False)
        content.place(relx=0.5, rely=0.5, anchor="center")

        title = ctk.CTkLabel(
            content,
            text="Choose your language",
            font=("Zalando Sans Expanded SemiBold", 17),
            text_color=self.ink,
            height=22,
        )
        title.place(relx=0.5, y=0, anchor="n")

        row = ctk.CTkFrame(content, width=326, height=76, fg_color="transparent")
        row.pack_propagate(False)
        row.place(relx=0.5, y=32, anchor="n")

        accent = "#C26AAA"
        border = "#694B66" if self.dark else "#A87AA1"
        button_bg = self.panel_color
        button_hover = self.card_color

        def choose(value):
            self.change_language(value)
            try:
                closed(False)
            except TypeError:
                closed()
            self.after(55, self.welcome_dialog)

        def continue_current(event=None):
            current = "ind" if self.lang == "id" else "eng"
            choose(current)
            return "break"

        def language_card(x, label, value, greeting):
            card = ctk.CTkButton(
                row,
                text=label,
                command=lambda v=value: choose(v),
                width=153,
                height=50,
                corner_radius=8,
                border_width=2,
                border_color=border,
                fg_color=button_bg,
                hover_color=button_hover,
                text_color=accent,
                font=("Red Hat Display Bold", 14),
            )
            card.place(x=x, y=0)

            ctk.CTkLabel(
                row,
                text=greeting,
                font=("Red Hat Display Light", 10),
                text_color=self.ink,
                height=14,
            ).place(x=x + 76.5, y=57, anchor="n")

        language_card(5, "English", "eng", "Hey there!")
        language_card(168, "Indonesia", "ind", "Halo, kamu!")

        # Skip = click the dim area outside or press Escape.
        win.close_panel = continue_current
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.bind("<Escape>", continue_current)

        shade = getattr(win, "_lena_shade", None)
        if shade is not None:
            shade.bind("<Button-1>", continue_current)

    def replay_welcome(self):
        # Settings is a persistent custom dialog. Retire it cleanly before
        # replaying onboarding so the new chooser cannot reuse its body/state.
        current = getattr(self, "modal", None)
        if current is not None:
            destroy_now = getattr(current, "_lena_destroy_now", None)
            if destroy_now:
                try:
                    destroy_now(False)
                except (tk.TclError, TypeError):
                    pass
            else:
                try:
                    current.destroy()
                except tk.TclError:
                    pass
                if self.modal is current:
                    self.modal = None
        self.after(90, lambda: self.language_dialog(replay=True))

    def welcome_dialog(self):
        win, body, closed = self.dialog("LENA", 610, 290)
        if getattr(win, "_lena_content_built", False):
            return
        win._lena_content_built = True
        self.label(
            body, self.words("Selamat datang di LENA", "Welcome to LENA"), 26, "Bold"
        ).pack(pady=20)
        self.label(
            body,
            self.words(
                "Basic dan Image Upscale siap digunakan. Download Better, Best, atau Hair & Fur hanya saat diperlukan.",
                "Basic and Image Upscale are ready to use. Download Better, Best, or Hair & Fur only when needed.",
            ),
            16,
            wraplength=510,
            justify="center",
        ).pack(pady=15)

        def done():
            self.settings["onboarded"] = True
            self.persist()
            closed()

        win.close_panel = done
        win.protocol("WM_DELETE_WINDOW", done)
        self.outline_button(
            body, self.words("Mulai dengan Basic", "Start with Basic"), done, width=200
        ).pack(pady=16)

    def open_models(self):
        if self.task != "remove":
            return
        if self.manager_window:
            self.dismiss_popup()
            return
        self.dismiss_popup()
        scale = self.sidebar._get_widget_scaling()
        name_width = (
            max(
                tkfont.Font(
                    family="Red Hat Display Light", size=-round(13 * scale)
                ).measure(MODELS[m][0])
                / scale
                for m, _ in QUALITIES
            )
            + 16
        )
        width = max(410, name_width + 251)
        panel = ctk.CTkFrame(
            self.workspace,
            width=width,
            height=min(440, self.viewer.winfo_height() / scale - 16),
            fg_color=self.panel_color,
            corner_radius=10,
            border_width=1,
            border_color="#74717A",
        )
        panel.pack_propagate(False)
        self.popup = self.manager_window = panel
        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=14, pady=12)
        self.outline_button(
            footer,
            self.words("Buka Folder Model", "Open Models Folder"),
            self.open_cache,
            width=130,
        ).pack(side="left")

        def download_all_missing():
            missing = [
                m for m in ("birefnet-lite", "mvanet", REFINER) if path(m) is None
            ]
            if missing and not self.busy:
                self.download_models(missing)

        self.manager_download_all = self.outline_button(
            footer, "", download_all_missing, width=154
        )
        self.manager_download_all.configure(
            border_color="#3294F5",
            text_color="#65B5FF" if self.dark else "#1478D4",
            hover_color="#24394D" if self.dark else "#DCEEFF",
        )
        self.manager_download_all.pack(side="right")
        body = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            scrollbar_button_color=self.panel_color,
            scrollbar_button_hover_color=self.muted,
        )
        body.pack(fill="both", expand=True, padx=(12, 4), pady=(14, 0))
        self.manager_body = body
        self.label(
            body,
            self.t("model_explanation"),
            13,
            wraplength=width - 40,
            justify="center",
        ).pack(fill="x", pady=(0, 12))
        self.manager_rows = {}
        for model, tier in (*QUALITIES, (REFINER, "Hair & fur")):
            card = ctk.CTkFrame(body, fg_color=self.card_color, corner_radius=9)
            card.pack(fill="x", pady=6)
            self.label(card, tier, 15, "SemiBold").pack(
                anchor="w", padx=14, pady=(8, 0)
            )
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=8)
            row.grid_columnconfigure(0, weight=1)
            self.label(
                row,
                MODELS[model][0] + " · " + size_text(model),
                13,
                "Light",
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            button = self.button(
                row,
                "",
                lambda m=model: self.download_models([m]),
                width=84,
                color="#173D2A",
            )
            button.configure(
                height=25, font=("Red Hat Display SemiBold", 13), text_color="#BDF5D2"
            )
            button.grid(row=0, column=1, padx=(10, 0))
            self.manager_rows[model] = button
        self.refresh_manager()
        self.wheel_router.walk(panel)
        available = self.workspace.winfo_width() / scale
        trigger_x = (
            self.models_button.winfo_rootx() - self.workspace.winfo_rootx()
        ) / scale
        final_x = max(8, min(available - width - 8, trigger_x))
        # Parent is still unmapped here, so build/layout once and show directly.
        # No placeholder flash, but also no artificial slide delay.
        panel.update_idletasks()
        rounded_widget(panel, 10)
        panel.place(x=final_x, y=8)
        panel.lift()

    def refresh_manager(self):
        super().refresh_manager()
        if self.manager_window:
            for m, b in self.manager_rows.items():
                if path(m) is not None:
                    b.configure(text=self.words("Siap", "Ready"))
                elif not self.busy:
                    b.configure(text=self.words("Download", "Download"))
            all_button = getattr(self, "manager_download_all", None)
            if all_button is not None and all_button.winfo_exists():
                missing = [
                    m for m in ("birefnet-lite", "mvanet", REFINER) if path(m) is None
                ]
                remaining = sum(size(m) for m in missing)
                mb = round(remaining / 1e6)
                all_button.configure(
                    text=f"{self.words('Download Semua','Download All')} · {mb} MB",
                    state="disabled" if self.busy or not missing else "normal",
                    border_color="#3294F5",
                    text_color="#65B5FF" if self.dark else "#1478D4",
                    text_color_disabled="#65B5FF" if self.dark else "#1478D4",
                )
