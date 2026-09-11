"""Process-lifetime cache for torch models that cannot be reconstructed.

PyTorch 2.6 raises ``Only a single TORCH_LIBRARY can be used to register the
namespace`` when InsightFace R100, HuggingFace ViT (age), or AdaFace/DFA are
built a second time in the same process. Pytest resets ``ModelRegistry``
between files and calls ``close()``, which used to delete those modules.

Keep constructed torch graphs for the process lifetime. Wrappers may be
recreated; the underlying modules are reused.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")

# Registry keys whose instances must survive ``unload_all`` / ``reset_for_tests``.
PINNED_REGISTRY_NAMES = frozenset(
    {
        "arcface_r100",
        "adaface_vit_kprpe",
        "age_detector",
    }
)

_VALUES: dict[str, Any] = {}
_LOCK = threading.Lock()


def get_cached(key: str) -> Any | None:
    """Return a cached value, or ``None`` if it has not been stored."""
    with _LOCK:
        return _VALUES.get(key)


def get_or_create(key: str, factory: Callable[[], T]) -> T:
    """Return the cached value for ``key``, calling ``factory`` once if missing."""
    with _LOCK:
        existing = _VALUES.get(key)
        if existing is not None:
            return cast(T, existing)
        created = factory()
        _VALUES[key] = created
        return created


def pin_registry_model(name: str, model: Any) -> None:
    """Keep a registry-loaded torch model for later ``get_model`` calls."""
    if name not in PINNED_REGISTRY_NAMES or model is None:
        return
    with _LOCK:
        _VALUES.setdefault(f"registry:{name}", model)


def get_pinned_registry_model(name: str) -> Any | None:
    """Return a previously pinned registry model, if any."""
    if name not in PINNED_REGISTRY_NAMES:
        return None
    with _LOCK:
        return _VALUES.get(f"registry:{name}")


def is_pinned_registry_name(name: str) -> bool:
    """Return True when ``name`` must not be destroyed on registry unload."""
    return name in PINNED_REGISTRY_NAMES


def clear_pinned_registry_model(name: str) -> None:
    """Drop a pinned registry instance (pytest helper)."""
    with _LOCK:
        _VALUES.pop(f"registry:{name}", None)
