"""Local ONNX preparation. Never downloads or executes Python model code."""

from pathlib import Path


def cpu_model(source):
    import onnx
    import numpy as np
    from onnx import TensorProto, numpy_helper

    source = Path(source)
    target = source.with_name("cpu-fp32.onnx")
    if target.is_file():
        return target
    model = onnx.load(str(source), load_external_data=True)

    def tensor(t):
        if t.data_type == TensorProto.FLOAT16:
            array = numpy_helper.to_array(t).astype(np.float32)
            t.CopyFrom(numpy_helper.from_array(array, t.name))

    def graph(g):
        for t in g.initializer:
            tensor(t)
        for item in [*g.input, *g.output, *g.value_info]:
            if item.type.tensor_type.elem_type == TensorProto.FLOAT16:
                item.type.tensor_type.elem_type = TensorProto.FLOAT
        for n in g.node:
            for a in n.attribute:
                if (
                    n.op_type == "Cast"
                    and a.name == "to"
                    and a.i == TensorProto.FLOAT16
                ):
                    a.i = TensorProto.FLOAT
                if a.type == onnx.AttributeProto.TENSOR:
                    tensor(a.t)
                elif a.type == onnx.AttributeProto.GRAPH:
                    graph(a.g)
                elif a.type == onnx.AttributeProto.GRAPHS:
                    for sub in a.graphs:
                        graph(sub)

    graph(model.graph)
    temp = target.with_suffix(".tmp.onnx")
    try:
        onnx.save(model, str(temp))
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return target
