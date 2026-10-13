"""Disposable inference workers protect the UI and isolate GPU failures."""

import json, os, sys, time, tempfile, subprocess, threading, atexit
from pathlib import Path
from PIL import Image
from lena_config import HOME
from lena_downloads import Cancelled
from lena_safety import candidates, record_failure
from lena_capabilities import gpu_supported

_failed_devices = set()
# LENA favors a small post-process footprint over keeping inference models warm.
# A completed job releases the reusable worker immediately; the next run reloads it.
MATTING_TIMEOUT = 120


def run_request(file, cache=None):
    request = json.loads(Path(file).read_text())
    work = Path(file).parent

    def stage(text):
        temp = work / "stage.tmp"
        temp.write_text(text)
        # Windows can briefly hold the destination while the UI polls it.
        # Progress is best effort and must never fail successful inference.
        for attempt in range(5):
            try:
                temp.replace(work / "stage")
                return
            except PermissionError:
                time.sleep(0.005)

    try:
        import numpy as np
        from lena_models import MODELS, path

        name = request["model"]
        source = path(name)
        if source is None:
            raise IOError("Model not prepared")
        if request.get("convert"):
            stage("compatibility")
            from lena_convert import cpu_model

            source = cpu_model(source)
        stage("loading")
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2) - 1))
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.log_severity_level = 3
        if request["backend"] == "dml":
            options.enable_mem_pattern = False
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            providers = [
                ("DmlExecutionProvider", {"device_id": str(request["device"]["id"])}),
                "CPUExecutionProvider",
            ]
        else:
            providers = ["CPUExecutionProvider"]
        key = (
            str(source),
            source.stat().st_mtime_ns,
            request["backend"],
            request.get("device", {}).get("id"),
        )
        session = (
            cache.get("session")
            if cache is not None and cache.get("key") == key
            else None
        )
        if session is None:
            if cache is not None:
                cache.clear()
            session = ort.InferenceSession(
                str(source), sess_options=options, providers=providers
            )
            if cache is not None:
                cache.update(key=key, session=session)
        if (
            request["backend"] == "dml"
            and "DmlExecutionProvider" not in session.get_providers()
        ):
            raise RuntimeError("GPU could not initialize")
        session.disable_fallback()
        stage("processing")
        with Image.open(work / "input.png") as image:
            original = image.convert("RGBA")
        if name == "span":
            from lena_upscale import upscale

            def progress(done, total):
                stage(f"upscale:{done}:{total}")

            output = upscale(original, session, request.get("scale", 4), progress)
            try:
                from lena_refine import finish_upscale

                output = finish_upscale(output)
            except Exception:
                pass
            stage("finishing")
            output.save(work / "output.png", compress_level=1)
            (work / "done.json").write_text(json.dumps({"backend": request["backend"]}))
            return 0
        default = MODELS[name][3]
        meta = session.get_inputs()[0]
        height = (
            meta.shape[2]
            if isinstance(meta.shape[2], int) and meta.shape[2] > 0
            else default
        )
        width = (
            meta.shape[3]
            if isinstance(meta.shape[3], int) and meta.shape[3] > 0
            else default
        )
        pixels = np.asarray(
            original.convert("RGB").resize(
                (width, height),
                (
                    Image.Resampling.BILINEAR
                    if name == "mvanet"
                    else Image.Resampling.LANCZOS
                ),
            ),
            dtype=np.float32,
        )
        kind = MODELS[name][4]
        if kind == "isnet":
            # IS-Net General official preprocessing: RGB resized to 1024x1024,
            # then normalized with mean=128 and std=256 (no 1/255 rescale).
            pixels = (pixels - 128.0) / 256.0
        else:
            pixels /= 255.0
            pixels -= np.array([0.485, 0.456, 0.406], dtype=np.float32)
            pixels /= np.array([0.229, 0.224, 0.225], dtype=np.float32)
        dtype = np.float16 if meta.type == "tensor(float16)" else np.float32
        tensor = pixels.transpose(2, 0, 1)[None].astype(dtype)
        outputs = session.run(None, {meta.name: tensor})
        mask = np.squeeze(outputs[0]).astype(np.float32)
        if kind == "logits":
            mask = 1 / (1 + np.exp(-np.clip(mask, -80, 80)))
        if mask.ndim != 2 or not np.isfinite(mask).all():
            raise RuntimeError("Invalid model result")
        stage("finishing")
        alpha = Image.fromarray((np.clip(mask, 0, 1) * 255).astype("uint8")).resize(
            original.size, Image.Resampling.LANCZOS
        )
        # Preserve any transparency already present in the source.
        matting_source = original.copy() if request.get("hair_fur", False) else None
        from lena_refine import finish_cutout, validate_alpha

        original = finish_cutout(original, alpha)
        matting_warning = None
        if request.get("hair_fur", False):
            # Keep a valid cutout if refinement fails, times out or exits natively.
            original.save(work / "base-output.png", compress_level=1)
            stage("matting")
            # Do not hold an ONNX graph/VRAM and the matting solver together.
            if cache is not None:
                cache.clear()
            del session, outputs, tensor, pixels, mask
            try:
                from lena_hair import refine_hair

                original = refine_hair(matting_source, alpha)
            except Exception as error:
                matting_warning = str(error)
                with Image.open(work / "base-output.png") as base:
                    original = base.copy()
                from lena_diagnostics import record

                record("matting_fallback", error=matting_warning)
        validation = validate_alpha(original.getchannel("A"))
        stage("finishing")
        original.save(work / "output.png", compress_level=1)
        (work / "done.json").write_text(
            json.dumps(
                {
                    "backend": request["backend"],
                    "gpu": request.get("device", {}).get("name", ""),
                    "matting": bool(request.get("hair_fur", False)),
                    "matting_warning": matting_warning,
                    "validation_warning": bool(validation.get("warning")),
                    "validation_reason": validation.get("reason"),
                }
            )
        )
        return 0
    except Exception:
        if cache is not None:
            cache.clear()
        import traceback

        (work / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def command(request):
    return [
        sys.executable,
        *(
            []
            if getattr(sys, "frozen", False)
            else [str(Path(__file__).with_name("lena_app.py"))]
        ),
        "--worker",
        str(request),
    ]


def serve():
    cache = {}
    reader = sys.stdin
    if reader is None and os.name == "nt":
        # Windowed frozen Python sets sys.stdin=None; use the inherited pipe.
        import ctypes, msvcrt

        kernel = ctypes.WinDLL("kernel32")
        kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
        kernel.GetStdHandle.restype = ctypes.c_void_p
        handle = kernel.GetStdHandle(-10)
        reader = os.fdopen(
            msvcrt.open_osfhandle(handle, os.O_RDONLY), "r", encoding="utf-8"
        )
    for line in reader:
        file = line.strip()
        if not file:
            continue
        code = run_request(file, cache)
        (Path(file).parent / "finished").write_text(str(code))


class Host:
    """One reusable session, never a growing pool of loaded models."""

    def __init__(self):
        self.child = None
        self.key = None
        self.lock = threading.RLock()
        self.log = None
        self.serial = 0

    def stop(self):
        with self.lock:
            if self.child is not None:
                try:
                    if self.child.poll() is None:
                        self.child.terminate()
                    try:
                        self.child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.child.kill()
                        self.child.wait(timeout=5)
                finally:
                    if self.child.stdin:
                        self.child.stdin.close()
                    self.child = None
                    self.key = None
            if self.log:
                self.log.close()
                self.log = None

    def start(self, key):
        self.serial += 1
        if self.child is not None and self.child.poll() is None and self.key == key:
            return
        self.stop()
        self.log = (HOME / "worker.log").open("w", encoding="utf-8")
        args = [
            sys.executable,
            *(
                []
                if getattr(sys, "frozen", False)
                else [str(Path(__file__).with_name("lena_app.py"))]
            ),
            "--serve",
        ]
        self.child = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=self.log,
            stderr=self.log,
            text=True,
            encoding="utf-8",
            creationflags=(
                (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                if os.name == "nt"
                else 0
            ),
        )
        self.key = key


_host = Host()


def shutdown():
    _host.stop()


atexit.register(shutdown)


def process(image, model, mode, devices, report, cancel, scale=4, hair_fur=False):
    with _host.lock:
        return _process(image, model, mode, devices, report, cancel, scale, hair_fur)


def _process(image, model, mode, devices, report, cancel, scale=4, hair_fur=False):
    if cancel.is_set():
        raise Cancelled()
    HOME.mkdir(parents=True, exist_ok=True)
    eligible = (
        candidates(model, devices) if mode == "auto" and gpu_supported(model) else []
    )
    attempts = [
        ("dml", device, False)
        for device in eligible
        if (model, device["name"]) not in _failed_devices
    ]
    attempts += [("cpu", {}, False)]
    if model == "birefnet-lite":
        attempts.append(("cpu", {}, True))
    with tempfile.TemporaryDirectory(
        prefix="job-", dir=HOME, ignore_cleanup_errors=True
    ) as workdir:
        work = Path(workdir)
        image.save(work / "input.png", compress_level=1)
        failed_gpu = False
        for backend, device, convert in attempts:
            if cancel.is_set():
                raise Cancelled()
            request = work / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "model": model,
                        "backend": backend,
                        "device": device,
                        "convert": convert,
                        "scale": scale,
                        "hair_fur": bool(hair_fur),
                    }
                )
            )
            for name in (
                "done.json",
                "error.txt",
                "stage",
                "output.png",
                "finished",
                "base-output.png",
            ):
                (work / name).unlink(missing_ok=True)
            report("backend", device.get("name", "CPU"))
            _host.start((model, backend, device.get("id"), convert))
            last = ""
            refining_since = None
            try:
                _host.child.stdin.write(str(request) + "\n")
                _host.child.stdin.flush()
                while _host.child.poll() is None and not (work / "finished").exists():
                    if cancel.is_set():
                        raise Cancelled()
                    try:
                        value = (work / "stage").read_text()
                        if value != last:
                            report("stage", value)
                            last = value
                            if value == "matting":
                                refining_since = time.monotonic()
                        if (
                            refining_since is not None
                            and time.monotonic() - refining_since > MATTING_TIMEOUT
                        ):
                            _host.stop()
                            break
                    except OSError:
                        pass
                    time.sleep(0.04)
                if cancel.is_set():
                    raise Cancelled()
            except BaseException:
                _host.stop()
                raise
            if (work / "done.json").exists() and (work / "finished").exists():
                metadata = json.loads((work / "done.json").read_text())
                if metadata.get("matting_warning"):
                    report("matting_warning", metadata["matting_warning"])
                if metadata.get("validation_warning"):
                    report(
                        "validation_warning", metadata.get("validation_reason") or True
                    )
                with Image.open(work / "output.png") as result:
                    output = result.copy()
                # Do not keep ONNX sessions resident after showing a result.
                # The old 60 s warm-worker window was the main reason LENA stayed
                # hundreds of MB above idle until the user cleared the photo.
                _host.stop()
                return output, device.get("name", "CPU"), failed_gpu
            if hair_fur and (work / "base-output.png").exists():
                _host.stop()
                report(
                    "matting_warning",
                    "Refinement worker stopped or exceeded its time limit",
                )
                from lena_diagnostics import record

                record("matting_worker_stopped", model=model)
                with Image.open(work / "base-output.png") as base:
                    return base.copy(), device.get("name", "CPU"), failed_gpu
            detail = (
                (work / "error.txt").read_text(encoding="utf-8")
                if (work / "error.txt").exists()
                else f"Worker exit {_host.child.returncode}"
            )
            _host.stop()
            try:
                (HOME / "last-error.log").write_text(detail, encoding="utf-8")
            except OSError:
                pass
            if backend == "dml":
                try:
                    record_failure(model, device, detail)
                except OSError:
                    pass
                _failed_devices.add((model, device["name"]))
                failed_gpu = True
                report("stage", "fallback")
        raise RuntimeError("Model inference failed")
