import json, os, sys, shutil
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
from lena_platform import data_home

HOME = data_home()
if not os.environ.get("LENA_DATA_DIR"):
    # Keep preferences and downloaded models when upgrading from the old name.
    legacy_home = HOME.with_name("LENA Enhanced")
    if legacy_home.is_dir():
        try:
            if not HOME.exists():
                legacy_home.rename(HOME)
            elif HOME.is_dir():

                def merge_legacy(source, destination):
                    for item in source.iterdir():
                        target = destination / item.name
                        try:
                            if not target.exists():
                                item.rename(target)
                            elif (
                                item.is_dir()
                                and target.is_dir()
                                and not item.is_symlink()
                            ):
                                merge_legacy(item, target)
                            elif (
                                item.name == "settings.json"
                                and item.is_file()
                                and item.stat().st_mtime > target.stat().st_mtime
                            ):
                                shutil.copy2(item, target)
                        except OSError:
                            pass
                    try:
                        source.rmdir()
                    except OSError:
                        pass

                merge_legacy(legacy_home, HOME)
        except OSError:
            pass
CACHE = HOME / "models"
SETTINGS = HOME / "settings.json"
os.environ.setdefault("OMP_NUM_THREADS", str(min(4, os.cpu_count() or 1)))
os.environ.setdefault("NUMBA_NUM_THREADS", str(min(4, os.cpu_count() or 1)))
os.environ.setdefault("NUMBA_CACHE_DIR", str(HOME / "matting-cache"))


def read_settings():
    try:
        value = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(value):
    HOME.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(SETTINGS)
