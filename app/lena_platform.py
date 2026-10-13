"""Small OS adapters; all visual widgets and animations remain shared."""

import os
import sys
import subprocess
from pathlib import Path

IS_MAC = sys.platform == "darwin"


def data_home():
    if os.environ.get("LENA_DATA_DIR"):
        return Path(os.environ["LENA_DATA_DIR"]).expanduser()
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "LENA"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LENA"


def open_local(path):
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["/usr/bin/open" if IS_MAC else "xdg-open", str(path)])


def wheel_amount(delta):
    return -delta if IS_MAC else -delta / 120 * 3


def register_fonts(folder):
    import ctypes as c

    if os.name == "nt":
        for font in folder.glob("*.ttf"):
            c.windll.gdi32.AddFontResourceExW(str(font), 0x10, 0)
    elif IS_MAC:
        cf = c.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        ct = c.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
            c.c_void_p,
            c.c_char_p,
            c.c_long,
            c.c_bool,
        ]
        cf.CFURLCreateFromFileSystemRepresentation.restype = c.c_void_p
        cf.CFRelease.argtypes = [c.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.argtypes = [
            c.c_void_p,
            c.c_uint,
            c.POINTER(c.c_void_p),
        ]
        ct.CTFontManagerRegisterFontsForURL.restype = c.c_bool
        for font in folder.glob("*.ttf"):
            raw = os.fsencode(font.resolve())
            url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
            if url:
                try:
                    ct.CTFontManagerRegisterFontsForURL(url, 1, None)
                finally:
                    cf.CFRelease(url)
