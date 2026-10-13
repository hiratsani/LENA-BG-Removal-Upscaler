"""Collect notices from the installed dependencies and checked-in licenses."""

from importlib import metadata
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PACKAGES = (
    "customtkinter",
    "darkdetect",
    "numpy",
    "onnxruntime-directml",
    "Pillow",
    "requests",
    "certifi",
    "charset-normalizer",
    "idna",
    "urllib3",
    "onnx",
    "protobuf",
    "ml_dtypes",
    "flatbuffers",
    "packaging",
    "typing_extensions",
    "coloredlogs",
    "humanfriendly",
    "sympy",
    "mpmath",
    "tkinterdnd2",
    "pyinstaller",
    "pefile",
)


def make_notices():
    chunks = [
        "LENA — Third-party software and model notices\nCopyright (c) 2026 Hiratsani\n",
        "LENA's original application and website code use the MIT license.\n"
        "Models, fonts and dependencies retain their upstream licenses.\n"
        "Model provenance and integrity pins are recorded in assets/models.json and MODEL-GUIDE.md.\n",
        "\n=== LENA ===\n" + (ROOT.parent / "LICENSE").read_text(encoding="utf-8"),
    ]
    for name in PACKAGES:
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        chunks.append(f"\n=== {name} {distribution.version} ===\n")
        for file in sorted(distribution.files or [], key=str):
            lowered = str(file).lower()
            if any(
                token in lowered for token in ("license", "notice", "copying")
            ) and lowered.endswith(
                (".txt", ".md", ".rst", "license", "notice", "copying")
            ):
                try:
                    chunks.append(
                        distribution.locate_file(file).read_text(encoding="utf-8")
                    )
                except (OSError, UnicodeError):
                    continue
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        chunks.append("\n=== Python ===\n" + python_license.read_text(encoding="utf-8"))
    for file in sorted((ROOT / "assets/fonts").glob("*OFL.txt")):
        chunks.append(f"\n=== {file.name} ===\n" + file.read_text(encoding="utf-8"))
    for file in sorted((ROOT / "licenses").glob("*.txt")):
        chunks.append(f"\n=== {file.name} ===\n" + file.read_text(encoding="utf-8"))
    normalized = "\n".join(line.rstrip() for line in "\n".join(chunks).splitlines()).rstrip() + "\n"
    (ROOT / "THIRD-PARTY-NOTICES.txt").write_text(normalized, encoding="utf-8")
    print("Third-party notices generated")


if __name__ == "__main__":
    make_notices()
