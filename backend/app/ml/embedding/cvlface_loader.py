"""Load cvlface HuggingFace-exported models from local directories."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, cast

import structlog
import yaml
from omegaconf import OmegaConf

logger = structlog.get_logger(__name__)

_MIN_WEIGHT_BYTES = 100_000


def _candidate_weight_paths(model_dir: Path) -> list[Path]:
    """Return weight file candidates in preferred load order."""
    return [
        model_dir / "pretrained_model" / "model.pt",
        model_dir / "model.safetensors",
    ]


def _read_state_dict(weights_path: Path) -> dict[str, Any]:
    """Load a PyTorch or safetensors checkpoint from disk."""
    if weights_path.suffix == ".safetensors":
        import safetensors.torch

        return dict(safetensors.torch.load_file(str(weights_path)))

    import torch

    return dict(torch.load(weights_path, map_location="cpu", weights_only=True))


def _normalize_state_dict_keys(state_dict: dict[str, Any], network: Any) -> dict[str, Any]:
    """Strip HuggingFace wrapper prefixes so keys match the inner cvlface module."""
    model_keys = set(network.state_dict().keys())

    if state_dict.keys() and all(key.startswith("model.") for key in state_dict):
        stripped = {key.removeprefix("model."): value for key, value in state_dict.items()}
        if len(set(stripped.keys()) & model_keys) > len(set(state_dict.keys()) & model_keys):
            return stripped

    return state_dict


def _load_weights_into_network(network: Any, model_dir: Path) -> Path:
    """Try candidate weight files until one loads with sufficient key overlap."""
    model_key_count = len(network.state_dict())
    last_error: Exception | None = None

    for weights_path in _candidate_weight_paths(model_dir):
        if not weights_path.exists():
            continue

        if weights_path.stat().st_size < _MIN_WEIGHT_BYTES:
            continue

        try:
            state_dict = _normalize_state_dict_keys(_read_state_dict(weights_path), network)
            overlap = len(set(state_dict.keys()) & set(network.state_dict().keys()))
            if overlap == 0:
                continue

            result = network.load_state_dict(state_dict, strict=False)
            loaded_keys = model_key_count - len(result.missing_keys)
            if loaded_keys < model_key_count // 2:
                continue

            logger.info(
                "cvlface_weights_loaded",
                weights=str(weights_path),
                loaded_keys=loaded_keys,
                total_keys=model_key_count,
            )
            return weights_path
        except Exception as exc:
            last_error = exc
            logger.warning(
                "cvlface_weights_load_failed",
                weights=str(weights_path),
                error=str(exc),
            )

    message = f"No usable weight file found in {model_dir}"
    if last_error is not None:
        raise FileNotFoundError(message) from last_error
    raise FileNotFoundError(message)


def load_cvlface_model(model_dir: Path | str) -> Any:
    """Load a cvlface recognition or aligner model from a local directory.

    The model directories contain Python packages (``models`` or ``aligners``) that
    must be importable during load. This function mirrors pix-workers' working-directory
    pattern and prefers ``model.safetensors`` over a potentially truncated ``model.pt``.

    Args:
        model_dir: Path to ``cvlface_adaface_vit_base_kprpe_webface12m`` or
            ``cvlface_DFA_mobilenet``.

    Returns:
        Eval-mode ``torch.nn.Module`` ready for inference.

    Raises:
        FileNotFoundError: When the directory or weights are missing.
    """
    path = Path(model_dir).resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"cvlface model directory not found: {path}")

    config_path = path / "pretrained_model" / "model.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"cvlface config not found: {config_path}")

    cwd = os.getcwd()
    inserted = False
    try:
        os.chdir(path)
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
            inserted = True

        with config_path.open(encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle)
        model_conf = OmegaConf.create(raw_config)

        network: Any
        if (path / "models").is_dir():
            models_mod = importlib.import_module("models")
            get_model = cast(Any, models_mod.get_model)
            network = get_model(model_conf)
        elif (path / "aligners").is_dir():
            aligners_mod = importlib.import_module("aligners")
            get_aligner = cast(Any, aligners_mod.get_aligner)
            network = get_aligner(model_conf)
        else:
            raise FileNotFoundError(f"No models/ or aligners/ package in {path}")

        weights_path = _load_weights_into_network(network, path)
        network.eval()

        logger.info(
            "cvlface_model_loaded",
            model_dir=str(path),
            weights=str(weights_path),
        )
        return network
    finally:
        os.chdir(cwd)
        if inserted and sys.path and sys.path[0] == str(path):
            sys.path.pop(0)
