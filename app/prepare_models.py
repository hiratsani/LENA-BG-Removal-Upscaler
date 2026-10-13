"""Prepare the three offline models from pinned, verified upstream assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
MODEL_FILES = {
    "isnet-general": "isnet-general-int8.onnx",
    "span": "span.onnx",
    "vitmatte-small": "vitmatte-small-int8.onnx",
}


def valid(file, meta):
    if not file.is_file() or file.stat().st_size != meta["size"]:
        return False
    algorithm, expected = meta["hash"].split(":", 1)
    digest = hashlib.new(algorithm)
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == expected


def prepare(verify_only=False):
    manifest = json.loads((ASSETS / "models.json").read_text(encoding="utf-8"))
    for name, filename in MODEL_FILES.items():
        meta = manifest[name]
        target = ASSETS / filename
        if valid(target, meta):
            print(f"Verified: {filename}", flush=True)
            continue
        if verify_only:
            raise RuntimeError(
                f"{filename} is missing or invalid. Run prepare_models.py first."
            )
        print(
            f"Downloading {filename} ({meta['size'] / 1_000_000:.1f} MB)...", flush=True
        )
        request = urllib.request.Request(
            meta["url"], headers={"User-Agent": "LENA/1.0.0"}
        )
        temporary = None
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                with tempfile.NamedTemporaryFile(
                    dir=ASSETS, suffix=".part", delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    while block := response.read(1024 * 1024):
                        stream.write(block)
            if not valid(temporary, meta):
                raise RuntimeError(f"Size or SHA-256 mismatch for {filename}")
            os.replace(temporary, target)
            print(f"Verified: {filename}", flush=True)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check local models without downloading",
    )
    args = parser.parse_args()
    try:
        prepare(args.verify_only)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Model preparation failed: {error}\n")
