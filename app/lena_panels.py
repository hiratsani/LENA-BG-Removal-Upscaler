"""Compact model overlay and scrollable supporting windows."""

import os, tkinter as tk, webbrowser
import customtkinter as ctk
from lena_config import ROOT
from lena_models import MODELS, path
from lena_platform import open_local


class Panels:
    def dismiss_popup(self):
        if self._panel_job:
            self.after_cancel(self._panel_job)
            self._panel_job = None
        self.manager_window = None
        self.manager_rows = {}
        super().dismiss_popup()

    def refresh_manager(self):
        if not self.manager_window or not self.manager_window.winfo_exists():
            return
        for model, button in self.manager_rows.items():
            ready = path(model) is not None
            button.configure(
                text="Ready" if ready else "Download",
                state="disabled" if ready or self.busy else "normal",
                fg_color="transparent" if ready else "#173D2A",
                border_width=1,
                border_color="#48C97B",
                text_color_disabled="#00C96E" if self.dark else "#087344",
            )

    def manager_progress(self, done, total):
        for model, button in self.manager_rows.items():
            if MODELS[model][0] == self.active_download:
                button.configure(
                    text=f"{done/total:.0%}" if total else f"{done/1e6:.0f} MB"
                )

    def dialog(self, title, width=560, height=500):
        win, body, closed = super().dialog(title, width, height)

        def icon():
            if os.name == "nt" and win.winfo_exists():
                win.iconbitmap(str(ROOT / "assets/custom/blank.ico"))

        icon()
        win.after(250, icon)
        surface = "#282B31" if self.dark else "#F3F0F3"
        win.configure(fg_color=surface)
        body.configure(fg_color=surface)
        if hasattr(self, "wheel_router"):
            self.wheel_router.walk(win)
        return win, body, closed

    def heading(self, body, text):
        ctk.CTkLabel(
            body,
            text=text,
            font=("Red Hat Display", 21, "bold"),
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(fill="x", padx=13, pady=(16, 8))

    def paragraph(self, body, text, font=14):
        label = ctk.CTkLabel(
            body,
            text=text,
            font=("Red Hat Display", font),
            anchor="w",
            justify="left",
            wraplength=400,
        )
        label.pack(fill="x", padx=13, pady=8)
        body.bind(
            "<Configure>",
            lambda e: label.configure(
                wraplength=max(100, e.width / body._get_widget_scaling() - 34)
            ),
            add="+",
        )
        return label

    def open_settings(self):
        win, body, closed = self.dialog(self.t("settings"))
        self.heading(body, self.t("settings"))
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
                state="disabled" if self.busy else "normal",
            ).pack(anchor="w", padx=15, pady=10)
        self.paragraph(body, self.t("dml"))
        self.paragraph(
            body, "\n".join(d["name"] for d in self.devices) or self.t("no_gpu")
        )
        self.paragraph(body, self.t("gpu_failure_note"))
        self.button(body, self.t("models_folder"), self.open_cache, width=180).pack(
            anchor="w", padx=13, pady=8
        )
        self.paragraph(body, "LENA 1.0 · by Hiratsani © 2026\n" + self.t("offline"), 12)
        self.button(
            body,
            "Licenses",
            lambda: open_local(ROOT / "THIRD-PARTY-NOTICES.txt"),
            width=100,
        ).pack(anchor="w", padx=13, pady=8)

    def open_guide(self):
        win, body, closed = self.dialog(self.t("guide"), 570, 570)
        for title, key in [("remove_tab", "steps"), ("upscale_title", "upscale_steps")]:
            self.heading(body, self.t(title))
            self.paragraph(body, self.t(key))
        for key in ("transfer_guide", "offline"):
            self.paragraph(body, self.t(key))

    def welcome_dialog(self):
        win, body, closed = self.dialog("LENA", 570, 460)
        self.heading(body, self.t("welcome"))
        for key in ("welcome_body", "once"):
            self.paragraph(body, self.t(key))

        def done(models=False):
            self.settings["onboarded"] = True
            self.persist()
            closed()
            if models:
                self.open_models()

        self.button(
            body, self.t("models"), lambda: done(True), width=210, color="#945887"
        ).pack(pady=10)
        self.button(body, self.t("skip_hint"), done, width=210).pack(pady=8)
        win.protocol("WM_DELETE_WINDOW", done)

    def donate(self):
        win, body, closed = self.dialog("Buy me a coffee", 480, 215)

        # RedesignedPanels creates this support Toplevel hidden already.
        # Only set alpha here; withdrawing it again can make CTk recalculate
        # its requested size before the entrance animation.
        try:
            win.attributes("-alpha", 0)
        except tk.TclError:
            pass

        def animated_close():
            if getattr(win, "_coffee_closing", False):
                return
            win._coffee_closing = True

            def fade(step=10):
                if not win.winfo_exists():
                    return
                if step <= 0:
                    closed()
                    return
                try:
                    win.attributes("-alpha", step / 10)
                except tk.TclError:
                    closed()
                    return
                win.after(12, lambda: fade(step - 1))

            fade()

        win.close_panel = animated_close
        win.bind("<Escape>", lambda e: (win.close_panel(), "break")[1])

        # Plain frame instead of the inherited scrollable body: content here
        # never overflows, so a scrollbar track has no reason to show.
        inner = ctk.CTkFrame(body, fg_color="transparent")
        inner.pack(fill="both", expand=True)
        body.configure(
            scrollbar_button_color=self.panel_color,
            scrollbar_button_hover_color=self.panel_color,
        )
        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(pady=(4, 10))
        from PIL import Image

        try:
            heart = ctk.CTkImage(
                Image.open(ROOT / "assets/custom/love_gradient_56.png"), size=(24, 21)
            )
            ctk.CTkLabel(
                head,
                text="  Thank you for using LENA!",
                image=heart,
                compound="left",
                font=("Zalando Sans Expanded SemiBold", 18),
                text_color=self.ink if hasattr(self, "ink") else None,
            ).pack()
        except (OSError, FileNotFoundError):
            ctk.CTkLabel(
                head,
                text="\U0001f49f Thank you for using LENA!",
                font=("Zalando Sans Expanded SemiBold", 18),
                text_color=self.ink if hasattr(self, "ink") else None,
            ).pack()
        note = "I build and maintain LENA independently, and it\u2019s completely free.\nIf LENA helps you, consider supporting my work and future updates :D"
        ctk.CTkLabel(
            inner,
            text=note,
            font=("Red Hat Display", 13),
            justify="center",
            text_color=self.muted if hasattr(self, "muted") else None,
            wraplength=430,
        ).pack(pady=(0, 16))
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(pady=(0, 12))
        for label, url in [
            ("International", "https://buymeacoffee.com/hiratsani"),
            ("Indonesia", "https://saweria.co/hiratsani"),
        ]:
            b = ctk.CTkButton(
                row,
                text=label,
                command=lambda u=url: self.open_link(u, win.close_panel),
                width=130,
                height=34,
                corner_radius=8,
                font=("Red Hat Display Medium", 12),
                fg_color="transparent",
                text_color="#C783B8",
                border_width=1,
                border_color="#C783B8",
                hover_color=(
                    self.card_color if hasattr(self, "card_color") else "#3A2E3E"
                ),
            )
            b.pack(side="left", padx=5)
        share = ctk.CTkLabel(
            inner,
            text="Or help by sharing LENA with your friends",
            font=("Red Hat Display Medium", 12, "underline"),
            text_color=self.muted if hasattr(self, "muted") else None,
            cursor="hand2",
        )
        share.pack(pady=(2, 2))

        # Finish layout while still hidden. Do NOT query win.geometry() here:
        # CTk can report the tiny requested content size while withdrawn.
        win.update_idletasks()
        target = getattr(win, "_lena_target_geometry", None)
        if target is not None:
            width, height, x, y = target
        else:
            # Safe fallback for the support popup's designed dimensions.
            width, height = 480, 215
            x = max(
                0,
                self.winfo_rootx()
                + (self.winfo_width() - round(width * win._get_window_scaling())) // 2,
            )
            y = max(
                0,
                self.winfo_rooty()
                + (self.winfo_height() - round(height * win._get_window_scaling()))
                // 2,
            )
        size = f"{width}x{height}"
        offset = 18
        win.geometry(f"{size}+{x}+{y+offset}")

        def slide_in(step=0, total=10):
            if not win.winfo_exists():
                return
            if step > total:
                win.geometry(f"{size}+{x}+{y}")
                try:
                    win.attributes("-alpha", 1)
                except tk.TclError:
                    pass
                return
            t = step / total
            eased = 1 - (1 - t) ** 3
            try:
                win.attributes("-alpha", eased)
            except tk.TclError:
                return
            win.geometry(f"{size}+{x}+{round(y+offset*(1-eased))}")
            win.after(14, lambda: slide_in(step + 1, total))

        try:
            win.deiconify()
            win.lift()
        except tk.TclError:
            return
        win.after(10, slide_in)

    def open_link(self, url, close_panel):
        # Close the support popup before handing focus to an external browser.
        # This keeps the Toplevel lifecycle simple on Windows and avoids
        # the browser is only launched once it is fully gone. os.startfile is
        # used on Windows because it hands off and returns immediately,
        # unlike webbrowser.open which can block waiting on the new process.
        def launch():
            if os.name == "nt":
                try:
                    os.startfile(url)
                    return
                except OSError:
                    pass
            webbrowser.open(url)

        close_panel()
        self.after(120, launch)
