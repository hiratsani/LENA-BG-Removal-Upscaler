# LENA models

LENA's code is MIT-licensed. The model weights are third-party assets with their own licenses; LENA's license does not relicense them. No weights are committed to this repository.

| Feature | Pinned export | Preparation | License / upstream |
| --- | --- | --- | --- |
| Basic | IS-Net General INT8, 44.2 MB | `prepare_models.py` | [MIT — xrds / imgly](https://huggingface.co/xrds/isnet-general-onnx-int8) |
| Better | BiRefNet Lite FP16, 114.5 MB | Optional download in the app | [MIT — BiRefNet](https://github.com/ZhengPeng7/BiRefNet) / [ONNX export](https://huggingface.co/onnx-community/BiRefNet_lite-ONNX) |
| Best | MVANet INT8, 141.1 MB | Optional download in the app | [MIT — MVANet](https://github.com/qianyu-dlut/MVANet) / [ONNX export](https://huggingface.co/onnx-community/MVANet-ONNX) |
| Hair & Fur | ViTMatte Small Composition-1K quantized, 27.5 MB | `prepare_models.py` | [Apache-2.0 model card](https://huggingface.co/hustvl/vitmatte-small-composition-1k) / [Xenova ONNX export](https://huggingface.co/Xenova/vitmatte-small-composition-1k) |
| Upscale | 4xNomosUni SPAN MultiJPG FP32, 1.7 MB | `prepare_models.py` | [CC BY 4.0 — Philip Hofmann](https://huggingface.co/Phips/4xNomosUni_span_multijpg) |

All download URLs, sizes and SHA-256 hashes are recorded in [assets/models.json](assets/models.json). The three prepared models are included in a built installer, making those features available offline. Optional models live in the app's data directory, outside the install folder.

The official SPAN export is used unchanged, with tiled inference, separate alpha resizing, and downsampling for 2× output. ViTMatte refines the boundary using an automatically generated trimap; it does not replace foreground selection. Enable Hair & Fur when hair or fur is visible.

BiRefNet's pinned export returns logits, so the worker applies sigmoid. MVANet's pinned export already returns alphas, so sigmoid must not be applied twice. The runtime preserves original export dimensions for background removal and limits upscaling to 64 megapixels.

License texts are kept in `licenses/`; font licenses are kept beside the fonts. `make_notices.py` collects these with installed dependency notices for distribution. ViTMatte's upstream implementation code uses MIT; the published base model card specifies Apache-2.0 for its model weights.
