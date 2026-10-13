import ctypes, os
import tkinter as tk
from ctypes import wintypes as W
from contextlib import contextmanager

# Loaded and configured once at import time instead of on every call. On
# Windows, ctypes.WinDLL() for an already-loaded system DLL is cheap (the OS
# just bumps a refcount), but re-running .argtypes/.restype assignment on
# every rounded_widget()/atomic_redraw() call is redundant, idempotent work.
if os.name == "nt":
    _user32 = ctypes.WinDLL("user32")
    _gdi32 = ctypes.WinDLL("gdi32")
    _user32.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    _user32.RedrawWindow.argtypes = [W.HWND, ctypes.c_void_p, W.HRGN, W.UINT]
    _gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
    _gdi32.CreateRoundRectRgn.restype = W.HRGN
    _user32.SetWindowRgn.argtypes = [W.HWND, W.HRGN, W.BOOL]
    _user32.SetWindowRgn.restype = ctypes.c_int
    _gdi32.DeleteObject.argtypes = [W.HANDLE]
    _user32.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
    _user32.GetParent.argtypes = [W.HWND]
    _user32.GetParent.restype = W.HWND
else:
    _user32 = _gdi32 = None


@contextmanager
def atomic_redraw(*widgets):
    """Commit native child visibility changes in one paint pass on Windows."""
    if os.name != "nt":
        yield
        return
    user = _user32
    handles = [widget.winfo_id() for widget in widgets if widget.winfo_ismapped()]
    for hwnd in handles:
        user.SendMessageW(hwnd, 0x000B, 0, 0)
    try:
        yield
        if widgets:
            widgets[0].update_idletasks()
    finally:
        for hwnd in handles:
            user.SendMessageW(hwnd, 0x000B, 1, 0)
            user.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0400)


def rounded_widget(widget, radius, pill=False):
    """Clip the native child window so its corner background cannot form a box."""
    if os.name != "nt":
        return
    user = _user32
    gdi = _gdi32

    def update(event=None):
        if (
            isinstance(widget, tk.Toplevel)
            and event is not None
            and event.widget is not widget
        ):
            return
        if not widget.winfo_exists():
            return
        try:
            scale = widget._get_widget_scaling()
        except AttributeError:
            scale = (
                widget._get_window_scaling()
                if hasattr(widget, "_get_window_scaling")
                else 1
            )
        visual_radius = max(1.0, radius * scale)
        hwnd = widget.winfo_id()
        # CTkToplevel.winfo_width reports logical units; Win32 regions use pixels.
        if isinstance(widget, tk.Toplevel):
            hwnd = user.GetParent(hwnd) or hwnd
        rect = W.RECT()
        user.GetClientRect(hwnd, ctypes.byref(rect))
        if rect.right < 2 or rect.bottom < 2:
            return

        if pill:
            # For capsules/circles the old safety margin reduced the radius and
            # visibly squared the ends. Use the physical client height so the
            # native child window is a true pill/circle.
            diameter = max(2, rect.bottom + 1)
        else:
            # Cards keep the looser region so CTk's own antialiased corner is
            # not cut by the binary Win32 mask.
            clip_radius = max(1.0, visual_radius - max(1.5, 1.8 * scale))
            diameter = round(clip_radius * 2)

        region = gdi.CreateRoundRectRgn(
            0, 0, rect.right + 1, rect.bottom + 1, diameter, diameter
        )
        if region and not user.SetWindowRgn(hwnd, region, True):
            gdi.DeleteObject(region)

    widget.bind("<Configure>", update, add="+")
    # Try immediately (works once the widget has been inserted in its parent),
    # then repeat at idle as a safety net for CTk geometry propagation.
    update()
    widget.after_idle(update)
