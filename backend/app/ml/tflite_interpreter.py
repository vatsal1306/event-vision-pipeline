"""LiteRT interpreter factory for on-device TFLite models.

TensorFlow 2.20+ deprecates ``tf.lite.Interpreter`` in favour of the standalone
``ai-edge-litert`` package. All TFLite inference in this codebase should go
through :func:`create_tflite_interpreter`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_edge_litert.interpreter import Interpreter


def create_tflite_interpreter(
    model_path: Path | str,
    *,
    num_threads: int | None = None,
) -> Interpreter:
    """Create a LiteRT interpreter and allocate input/output tensors.

    Args:
        model_path: Filesystem path to a ``.tflite`` flatbuffer.
        num_threads: Optional thread count for CPU inference.

    Returns:
        An initialised LiteRT ``Interpreter`` ready for ``set_tensor`` / ``invoke``.

    Raises:
        FileNotFoundError: When ``model_path`` does not exist.
    """
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"TFLite model file not found: {path}")

    kwargs: dict[str, Any] = {"model_path": str(path)}
    if num_threads is not None:
        kwargs["num_threads"] = num_threads

    interpreter = Interpreter(**kwargs)
    interpreter.allocate_tensors()
    return interpreter
