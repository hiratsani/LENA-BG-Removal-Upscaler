"""Remove proven-unreferenced native duplicates, keeping DirectML and NumPy BLAS."""

from pathlib import Path
import pefile

root = Path(__file__).parent / ".build/dist/LENA/_internal"
used = set()
for p in (root / "numpy").rglob("*.pyd"):
    pe = pefile.PE(str(p))
    used.update(entry.dll.decode().lower() for entry in pe.DIRECTORY_ENTRY_IMPORT)
    pe.close()
for dll in (root / "numpy.libs").glob("*.dll"):
    if dll.name.lower() not in used:
        print("Remove unused BLAS", dll.name, dll.stat().st_size)
        dll.unlink()
# Python's pybind module does not load the standalone ONNX C API DLL.
# Bundled CPU and DirectML sessions are tested after this removal.
c_api = root / "onnxruntime/capi/onnxruntime.dll"
if c_api.exists():
    print("Remove standalone C API", c_api.stat().st_size)
    c_api.unlink()
# The file picker advertises PNG/JPEG/WebP/BMP/TIFF. The bundled AVIF codec is
# an optional Pillow extension and is much larger than the other codecs.
for avif in (root / "PIL").glob("_avif*.pyd"):
    print("Remove unused AVIF codec", avif.stat().st_size)
    avif.unlink()
