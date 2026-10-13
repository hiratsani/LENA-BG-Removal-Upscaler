"""Transparent cached PNG frames drawn on the photo's own Canvas."""

import time
from PIL import Image, ImageTk
from lena_config import ROOT
from lena_motion import motion_enabled


class LoadingLogo:
    def __init__(self, parent):
        self.parent = parent
        self.canvas = parent.surface
        self.frames = []
        self.cache_key = None
        self.job = None
        self.running = False
        self.frame_index = 0
        self.item = None
        self.canvas.bind("<Configure>", self.position, add="+")
        self.canvas.bind("<Destroy>", lambda e: self.stop(), add="+")

    def prepare(self, dark, size):
        key = (dark, size)
        if key == self.cache_key:
            return
        if self.item is not None:
            self.canvas.itemconfigure(self.item, image="")
        frames = []
        for path in sorted((ROOT / "assets/loading").glob("*.png")):
            with Image.open(path) as source:
                frame = source.convert("RGBA")
                frame.thumbnail((size, size), Image.Resampling.LANCZOS)
                frames.append(ImageTk.PhotoImage(frame, master=self.canvas))
        self.frames = frames
        self.cache_key = key

    def position(self, event=None):
        if self.running and self.item is not None:
            self.canvas.coords(self.item, self.parent.iw / 2, self.parent.ih / 2)
            self.canvas.tag_raise(self.item)

    def start(self, dark, size=72):
        self.stop()
        self.prepare(dark, size)
        if not self.frames:
            return
        self.item = self.canvas.create_image(0, 0, anchor="center")
        self.running = True
        self.started = time.monotonic()
        self.frame_index = 0
        self.tick()

    def tick(self):
        if not self.running:
            return
        self.frame_index = int((time.monotonic() - self.started) * 24) % len(
            self.frames
        )
        self.canvas.itemconfigure(self.item, image=self.frames[self.frame_index])
        self.position()
        self.job = self.canvas.after(42, self.tick) if motion_enabled() else None

    def stop(self):
        self.running = False
        if self.job:
            self.canvas.after_cancel(self.job)
            self.job = None
        if self.item is not None:
            self.canvas.delete(self.item)
            self.item = None

    def destroy(self):
        self.stop()
