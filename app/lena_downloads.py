"""Pinned downloads and atomic model preparation. No executable remote Python."""

import hashlib, json, os, time, uuid
from pathlib import Path
import requests
from lena_models import MANIFEST, folder, path


class Cancelled(Exception):
    pass


def download(url, target, digest=None, report=lambda n, t: None, cancel=None):
    if cancel and cancel.is_set():
        raise Cancelled()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + "." + uuid.uuid4().hex + ".part")
    checksum = expected = None
    if digest:
        algorithm, expected = digest.split(":", 1)
        checksum = hashlib.new(algorithm)
    try:
        with requests.get(url, stream=True, timeout=(20, 30)) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))
            done = 0
            last = 0
            with temp.open("wb") as output:
                for block in response.iter_content(1024 * 1024):
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    output.write(block)
                    if checksum is not None:
                        checksum.update(block)
                    done += len(block)
                    if time.monotonic() - last > 0.15:
                        report(done, total)
                        last = time.monotonic()
            if total and done != total:
                raise IOError("Download size mismatch")
            if checksum is not None and checksum.hexdigest() != expected:
                raise IOError("Download checksum mismatch")
            if cancel and cancel.is_set():
                raise Cancelled()
            temp.replace(target)
            report(done, total or done)
    finally:
        temp.unlink(missing_ok=True)
    return target


def prepare(name, report=lambda k, v: None, cancel=None):
    existing = path(name)
    if existing:
        return existing
    if name == "isnet-general":
        raise IOError("Bundled model missing")
    meta = MANIFEST[name]
    if not meta.get("url") or not meta.get("hash"):
        raise IOError(
            meta.get("unavailable_reason", "Verified model download is not configured")
        )
    dest = folder(name)
    dest.mkdir(parents=True, exist_ok=True)
    staging = dest / "download.onnx"
    try:
        download(
            meta["url"],
            staging,
            meta["hash"],
            lambda n, t: report("download", (n, t)),
            cancel,
        )
        if staging.stat().st_size != meta["size"]:
            raise IOError("Model size mismatch")
        if cancel and cancel.is_set():
            raise Cancelled()
        (dest / "ready.json").unlink(missing_ok=True)
        os.replace(staging, dest / "model.onnx")
        marker = dest / "ready.tmp"
        marker.write_text(json.dumps({"hash": meta["hash"], "format": meta["format"]}))
        marker.replace(dest / "ready.json")
    finally:
        staging.unlink(missing_ok=True)
    return dest / "model.onnx"
