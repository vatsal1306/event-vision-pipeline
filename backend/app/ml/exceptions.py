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


class ClusteringLockError(MLException):
    """Raised when event clustering cannot use the Redis lock."""


class ClusteringLockBusyError(ClusteringLockError):
    """Raised when another clustering pass already holds the event lock."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            f"Clustering is already running for event {event_id}; retry after the lock expires."
        )
        self.event_id = event_id


class ClusterPersistenceError(MLException):
    """Raised when cluster rows cannot be written atomically."""

    def __init__(self, event_id: str, reason: str) -> None:
        super().__init__(f"Failed to persist clustering result for event {event_id}: {reason}")
        self.event_id = event_id
        self.reason = reason
