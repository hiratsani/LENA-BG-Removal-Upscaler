"""Persist GPU failure history so Auto does not repeatedly reset the display."""

import json, time, os
from pathlib import Path
from lena_config import HOME


def device_key(device):
    return f"{device.get('vendor',0)}:{device.get('name','')}"


def is_device_reset(detail):
    text = detail.lower()
    return any(
        code in text
        for code in (
            "887a0005",
            "887a0006",
            "887a0007",
            "dxgi_error_device",
            "gpu will not respond",
            "device removed",
            "device hung",
            "device reset",
        )
    )


def read_state():
    state = {}
    try:
        state = json.loads((HOME / "gpu-safety.json").read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        pass
    # Read-only inheritance: a separate profile must not retry a display adapter
    # that reset under the original LENA. Never modify the original profile.
    if "LENA_DATA_DIR" not in os.environ:
        try:
            legacy = Path(os.environ.get("LOCALAPPDATA", "")) / "LENA/gpu-safety.json"
            old = json.loads(legacy.read_text(encoding="utf-8"))
            for key, value in old.get("devices", {}).items():
                state.setdefault("devices", {}).setdefault(key, value)
            for key, models in old.get("models", {}).items():
                state.setdefault("models", {})[key] = list(
                    set(state.get("models", {}).get(key, [])) | set(models)
                )
        except (OSError, ValueError, AttributeError):
            pass
    return state


def save_state(state):
    HOME.mkdir(parents=True, exist_ok=True)
    target = HOME / "gpu-safety.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(target)


def candidates(model, devices):
    state = read_state()
    if not state.get("legacy_checked") and devices:
        try:
            detail = (HOME / "last-error.log").read_text(encoding="utf-8")
        except OSError:
            detail = ""
        if is_device_reset(detail):
            for device in devices:
                state.setdefault("devices", {})[device_key(device)] = {
                    "reason": "device-reset",
                    "time": time.time(),
                }
        state["legacy_checked"] = True
        try:
            save_state(state)
        except OSError:
            pass
    blocked = state.get("devices", {})
    failed = state.get("models", {})
    return [
        device
        for device in devices
        if device_key(device) not in blocked
        and model not in failed.get(device_key(device), [])
    ]


def record_failure(model, device, detail):
    state = read_state()
    key = device_key(device)
    if is_device_reset(detail):
        state.setdefault("devices", {})[key] = {
            "reason": "device-reset",
            "time": time.time(),
        }
    else:
        models = state.setdefault("models", {}).setdefault(key, [])
        if model not in models:
            models.append(model)
    save_state(state)
