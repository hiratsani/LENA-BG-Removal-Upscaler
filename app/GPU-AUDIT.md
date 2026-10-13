# Inference policy

The current `lena_capabilities.GPU_MODELS` set is empty: all pinned models in this release use CPU inference. The interface can detect graphics adapters, but adapter detection alone does not enable GPU processing.

The worker retains a DirectML path and CPU fallback for future verified exports. Before adding a model to the GPU allowlist, validate its exact file hash with the intended ONNX Runtime version and driver. Check successful inference, output quality, memory use, cancellation and worker shutdown. A model architecture's general GPU support is not evidence that a particular ONNX export works correctly with DirectML.

See [ONNX Runtime's DirectML documentation](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html). The runtime dependency is pinned in `requirements.txt`; the model exports are pinned in `assets/models.json`.
