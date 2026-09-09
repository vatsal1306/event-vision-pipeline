"""Thread-safe lazy model registry for Celery ML workers."""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable
from typing import Any

import structlog

from app.ml.config import MLConfig, get_ml_config
from app.ml.device import resolve_device
from app.ml.exceptions import ModelLoadError, ModelNotRegisteredError

logger = structlog.get_logger(__name__)

ModelLoader = Callable[["ModelRegistry"], Any]

_LOADERS: dict[str, ModelLoader] = {}
_LOADER_LOCK = threading.Lock()


def register_model_loader(model_name: str, loader: ModelLoader) -> None:
    """Register a lazy loader for a named model.

    Later ML stories register concrete loaders (for example ``scrfd`` in ML-002).

    Args:
        model_name: Registry key passed to ``ModelRegistry.get_model``.
        loader: Callable that receives the registry instance and returns the model.
    """
    with _LOADER_LOCK:
        _LOADERS[model_name] = loader


def unregister_model_loader(model_name: str) -> None:
    """Remove a model loader, primarily for test isolation."""
    with _LOADER_LOCK:
        _LOADERS.pop(model_name, None)


def clear_model_loaders() -> None:
    """Remove all registered model loaders (test helper)."""
    with _LOADER_LOCK:
        _LOADERS.clear()


def is_celery_worker_process() -> bool:
    """Return True when the current process is a Celery worker."""
    argv = " ".join(sys.argv).lower()
    return "celery" in argv and "worker" in argv


def is_test_process() -> bool:
    """Return True when code is running under pytest."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


class ModelRegistry:
    """Singleton registry that lazily loads and caches ML models per process."""

    _instance: ModelRegistry | None = None
    _instance_lock = threading.Lock()

    def __init__(self, config: MLConfig | None = None) -> None:
        self._config = config or get_ml_config()
        self._models: dict[str, Any] = {}
        self._model_lock = threading.RLock()

    @classmethod
    def get_instance(cls, config: MLConfig | None = None) -> ModelRegistry:
        """Return the process-wide registry singleton."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(config=config)
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        """Reset the singleton and unload cached models (pytest only)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.unload_all()
            cls._instance = None

    @property
    def config(self) -> MLConfig:
        """Active ML configuration for this registry."""
        return self._config

    @property
    def resolved_device(self) -> str:
        """Resolve the configured device without loading any models."""
        return resolve_device(self._config.device)

    def get_model(self, name: str) -> Any:
        """Return a cached model instance, loading it on first access.

        Args:
            name: Registered model key (for example ``scrfd``).

        Returns:
            The loaded model object.

        Raises:
            ModelNotRegisteredError: If no loader was registered for ``name``.
            ModelLoadError: If the loader raises during model initialisation.
        """
        self._ensure_load_allowed()

        if name in self._models:
            return self._models[name]

        with self._model_lock:
            if name in self._models:
                return self._models[name]

            loader = _LOADERS.get(name)
            if loader is None:
                raise ModelNotRegisteredError(name)

            try:
                model = loader(self)
            except Exception as exc:  # noqa: BLE001 — wrap all loader failures
                raise ModelLoadError(name, str(exc)) from exc

            self._models[name] = model
            logger.info("ml_model_loaded", model_name=name, device=self.resolved_device)
            return model

    def unload_all(self) -> None:
        """Drop cached models and call ``close``/``unload`` hooks when present."""
        with self._model_lock:
            for model_name, model in self._models.items():
                for method_name in ("unload", "close"):
                    cleanup = getattr(model, method_name, None)
                    if callable(cleanup):
                        try:
                            cleanup()
                        except Exception as exc:  # noqa: BLE001 — best-effort teardown
                            logger.warning(
                                "ml_model_unload_failed",
                                model_name=model_name,
                                method=method_name,
                                error=str(exc),
                            )
            self._models.clear()

    def _ensure_load_allowed(self) -> None:
        """Warn (or optionally block) when models load outside Celery workers."""
        if is_celery_worker_process() or is_test_process():
            return

        if self._config.strict_worker_only:
            raise ModelLoadError(
                "registry",
                "Model loading is restricted to Celery worker processes. "
                "Set ML_STRICT_WORKER_ONLY=false for local development.",
            )

        if self._config.warn_on_non_worker_load:
            logger.warning(
                "ml_model_load_outside_worker",
                hint="Models should normally load inside Celery workers only.",
            )


def get_model_registry(config: MLConfig | None = None) -> ModelRegistry:
    """Return the shared ``ModelRegistry`` singleton."""
    return ModelRegistry.get_instance(config=config)
