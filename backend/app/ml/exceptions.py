"""ML pipeline domain exceptions."""

from __future__ import annotations


class MLException(Exception):
    """Base exception for ML pipeline errors."""


class ModelNotRegisteredError(MLException):
    """Raised when ``get_model`` is called for an unknown model name."""

    def __init__(self, model_name: str) -> None:
        super().__init__(
            f"Model '{model_name}' is not registered. "
            f"Register a loader via register_model_loader() before calling get_model()."
        )
        self.model_name = model_name


class ModelLoadError(MLException):
    """Raised when a registered model fails to load."""

    def __init__(self, model_name: str, reason: str) -> None:
        super().__init__(f"Failed to load model '{model_name}': {reason}")
        self.model_name = model_name
        self.reason = reason
