from lena_platform import wheel_amount

"""Wheel routing before CTk's global bindings, including labels and cards."""
import customtkinter as ctk


class WheelRouter:
    def __init__(self, app):
        self.app = app
        self.fraction = {}
        self.tag = f"LenaWheel{id(app)}"
        app.bind_class(self.tag, "<MouseWheel>", self.route)
        app.bind("<Map>", lambda e: self.install(e.widget), add="+")
        self.walk(app)

    def install(self, widget):
        try:
            tags = widget.bindtags()
            if self.tag not in tags:
                widget.bindtags((self.tag,) + tags)
        except Exception:
            pass

    def walk(self, widget):
        self.install(widget)
        for child in widget.winfo_children():
            self.walk(child)

    def route(self, event):
        widget = event.widget
        target = None
        while widget is not None:
            if widget is self.app.viewer:
                return self.app.viewer.wheel(event)
            if isinstance(widget, ctk.CTkScrollableFrame):
                target = widget._parent_canvas
                break
            if widget is self.app.side:
                target = widget
                break
            widget = getattr(widget, "master", None)
        if target is None:
            return
        amount = self.fraction.get(target, 0) + wheel_amount(event.delta)
        steps = int(amount)
        self.fraction[target] = amount - steps
        if steps:
            target.yview_scroll(steps, "units")
        return "break"
