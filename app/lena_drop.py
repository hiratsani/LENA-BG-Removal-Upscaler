"""TkDND owns the native drop target; Python only receives Tk events."""

import tkinter as tk
import json, time, os, ctypes
from lena_config import HOME
from tkinterdnd2 import TkinterDnD, DND_FILES, COPY, REFUSE_DROP


class PhotoDrop:
    def __init__(self, root, callback, feedback):
        self.root = root
        self.callback = callback
        self.feedback = feedback
        self.active = False
        self.pending = None
        self.version = TkinterDnD.require(root)
        # Explorer can enter through the top-level HWND, not only the preview.
        self.target = root.viewer
        self.targets = (
            root,
            root.main,
            root.workspace,
            self.target,
            self.target.surface,
            self.target.placeholder,
        )
        self.registered = {}
        for target in self.targets:
            target.drop_target_register(DND_FILES)
            self.registered[str(target)] = target.winfo_id()
            for event in ("<<DropEnter>>", "<<DropPosition>>"):
                target.dnd_bind(event, self.enter)
            target.dnd_bind("<<DropLeave>>", self.leave)
            target.dnd_bind("<<Drop>>", self.drop)
            target.dnd_bind("<<Drop:DND_Files>>", self.drop)
            target.bind("<Map>", self.mapped, add="+")
        self.trace(
            "startup",
            version=self.version,
            elevated=(
                bool(ctypes.windll.shell32.IsUserAnAdmin())
                if os.name == "nt"
                else False
            ),
        )

    def trace(self, event, **fields):
        # Local diagnostics contain no image data or file paths.
        try:
            HOME.mkdir(parents=True, exist_ok=True)
            file = HOME / "drop-diagnostics.jsonl"
            if file.exists() and file.stat().st_size > 64000:
                file.write_text("", encoding="utf-8")
            with file.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(dict(time=time.time(), event=event, **fields)) + "\n"
                )
        except OSError:
            pass

    def mapped(self, event):
        target = event.widget
        if target not in self.targets:
            return
        handle = target.winfo_id()
        if self.registered.get(str(target)) != handle:
            target.drop_target_register(DND_FILES)
            self.registered[str(target)] = handle
            self.trace("registered_new_window")

    def available(self):
        return not self.root.busy and self.root.modal is None

    def show(self, active):
        if active == self.active:
            return
        self.active = active
        if self.pending:
            self.root.after_cancel(self.pending)

        def paint():
            self.pending = None
            if self.root.winfo_exists():
                self.feedback(self.active)

        self.pending = self.root.after(10, paint)

    def enter(self, event):
        allowed = self.available()
        self.show(allowed)
        if getattr(event, "event", "") == "<<DropEnter>>":
            self.trace(
                "enter",
                allowed=allowed,
                busy=self.root.busy,
                modal=self.root.modal is not None,
            )
        return COPY if allowed else REFUSE_DROP

    def leave(self, event=None):
        self.show(False)
        return COPY

    def drop(self, event):
        self.show(False)
        if not self.available():
            self.trace("rejected_busy")
            return REFUSE_DROP
        try:
            names = list(self.root.tk.splitlist(event.data))[:100]
        except (tk.TclError, ValueError, TypeError):
            self.trace("invalid_payload")
            return REFUSE_DROP
        if not names:
            return REFUSE_DROP
        self.trace("drop", count=len(names))
        # TkDND calls update idletasks inside OLE; timers leave that callback.
        self.root.after(
            10, lambda: self.callback(names) if self.root.winfo_exists() else None
        )
        return COPY
