import hashlib, json, os, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
import sys, atexit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_profile = tempfile.TemporaryDirectory(prefix="lena-tests-")
atexit.register(_profile.cleanup)
os.environ["LENA_DATA_DIR"] = _profile.name
import lena_models as models
import lena_downloads as downloads


class QualityTests(unittest.TestCase):
    def test_basic_bundled_and_legacy_selection_migrates(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "ROOT", Path(directory)),
        ):
            asset = Path(directory) / "assets/isnet-general-int8.onnx"
            asset.parent.mkdir()
            asset.write_bytes(b"basic fixture")
            with patch.dict(
                models.MANIFEST["isnet-general"], {"size": asset.stat().st_size}
            ):
                self.assertEqual(models.path("isnet-general"), asset)
        for name in ("ben2", "modnet", "isnet-anime", "lite-matting", "silueta"):
            self.assertNotIn(name, models.MODELS)
            self.assertIsNone(models.path(name))
            self.assertEqual(models.saved_quality({"model": name}), "isnet-general")

    def test_missing_saved_quality_falls_back(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "CACHE", Path(directory)),
        ):
            self.assertEqual(
                models.saved_quality({"quality": "mvanet"}), "isnet-general"
            )

    def test_cache_requires_matching_hash_and_size(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "CACHE", Path(directory)),
        ):
            dest = models.folder("mvanet")
            dest.mkdir()
            (dest / "model.onnx").write_bytes(b"bad")
            (dest / "ready.json").write_text(
                json.dumps({"hash": models.MANIFEST["mvanet"]["hash"]})
            )
            self.assertIsNone(models.path("mvanet"))
            (dest / "ready.json").write_text("broken")
            self.assertIsNone(models.path("mvanet"))

    def test_atomic_prepare_cancel_retry_restart(self):
        data = b"validated model fixture"
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        meta = {
            "url": "https://example.invalid/model",
            "hash": digest,
            "size": len(data),
            "format": "onnx",
            "filename": "model.onnx",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "CACHE", Path(directory)),
            patch.dict(models.MANIFEST, {"mvanet": meta}),
        ):
            cancel = threading.Event()

            def interrupted(url, target, *args):
                Path(target).write_bytes(data)
                cancel.set()

            with patch.object(downloads, "download", interrupted):
                with self.assertRaises(downloads.Cancelled):
                    downloads.prepare("mvanet", cancel=cancel)
            self.assertIsNone(models.path("mvanet"))
            self.assertFalse((models.folder("mvanet") / "download.onnx").exists())
            cancel.clear()
            with patch.object(
                downloads,
                "download",
                lambda url, target, *args: Path(target).write_bytes(data),
            ):
                downloads.prepare("mvanet", cancel=cancel)
            self.assertIsNotNone(models.path("mvanet"))
            with patch.object(
                downloads, "download", side_effect=AssertionError("Unexpected download")
            ):
                self.assertEqual(downloads.prepare("mvanet"), models.path("mvanet"))
            self.assertEqual(models.saved_quality({"quality": "mvanet"}), "mvanet")

    def test_download_integrity_failure_leaves_no_ready_model(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "CACHE", Path(directory)),
        ):
            with patch.object(
                downloads, "download", side_effect=IOError("Download checksum mismatch")
            ):
                with self.assertRaises(IOError):
                    downloads.prepare("mvanet")
            self.assertIsNone(models.path("mvanet"))

    def test_refiner_pinned_and_bundled_without_cache(self):
        self.assertEqual(models.REFINER, "vitmatte-small")
        self.assertTrue(models.MANIFEST[models.REFINER]["hash"].startswith("sha256:"))
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(models, "ROOT", Path(directory)),
            patch.object(models, "CACHE", Path(directory) / "cache"),
        ):
            asset = Path(directory) / "assets/vitmatte-small-int8.onnx"
            asset.parent.mkdir()
            asset.write_bytes(b"refiner fixture")
            with patch.dict(
                models.MANIFEST[models.REFINER], {"size": asset.stat().st_size}
            ):
                self.assertEqual(models.path(models.REFINER), asset)

    def test_vitmatte_preprocessing_and_padding(self):
        import numpy as np
        from PIL import Image
        from lena_hair import prepare_inputs

        image = Image.new("RGB", (65, 33), (255, 0, 128))
        tensor, trimap = prepare_inputs(image, Image.new("L", image.size, 128))
        self.assertEqual(tensor.shape, (1, 4, 64, 96))
        self.assertEqual(tensor.dtype, np.float32)
        np.testing.assert_allclose(
            tensor[0, :, 0, 0], [1, -1, (128 / 255 - 0.5) / 0.5, 128 / 255], atol=1e-6
        )
        self.assertTrue((tensor[:, :, 33:, :] == 0).all())
        self.assertTrue((tensor[:, :, :, 65:] == 0).all())
        for value in (0, 255):
            _, trimap = prepare_inputs(image, Image.new("L", image.size, value))
            self.assertTrue((trimap == value).all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
