"""Model loader registration for embedding extractors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ml.embedding.mode import resolve_embedding_mode
from app.ml.model_registry import ModelRegistry, register_model_loader

if TYPE_CHECKING:
    from app.ml.embedding.adaface_vit_kprpe import AdaFaceVitKprpe
    from app.ml.embedding.arcface_r100 import ArcFaceR100
    from app.ml.embedding.dual_embedder import DualEmbedder
    from app.ml.embedding.mobilefacenet import MobileFaceNetTFLite


def _load_arcface_r100(registry: ModelRegistry) -> ArcFaceR100:
    from app.ml.embedding.arcface_r100 import ArcFaceR100

    config = registry.config
    return ArcFaceR100(
        model_path=config.r100_model_path,
        device=registry.resolved_device,
    )


def _load_adaface_vit_kprpe(registry: ModelRegistry) -> AdaFaceVitKprpe:
    from app.ml.embedding.adaface_vit_kprpe import AdaFaceVitKprpe

    config = registry.config
    return AdaFaceVitKprpe(
        model_dir=config.adaface_model_path,
        aligner_dir=config.dfa_aligner_path,
        device=registry.resolved_device,
    )


def _load_mobilefacenet(registry: ModelRegistry) -> MobileFaceNetTFLite:
    from app.ml.embedding.mobilefacenet import MobileFaceNetTFLite

    config = registry.config
    return MobileFaceNetTFLite(model_path=config.mbf_model_path)


def _load_dual_embedder(registry: ModelRegistry) -> DualEmbedder:
    from app.ml.embedding.dual_embedder import DualEmbedder

    config = registry.config
    mode = resolve_embedding_mode(config)

    primary = registry.get_model("arcface_r100")
    fallback = registry.get_model("mobilefacenet")
    secondary = registry.get_model("adaface_vit_kprpe") if mode == "dual" else None

    return DualEmbedder(
        primary=primary,
        secondary=secondary,
        fallback=fallback,
        config=config,
    )


def register_embedding_loaders() -> None:
    """Register ArcFace, AdaFace, MBF, and dual embedder loaders."""
    register_model_loader("arcface_r100", _load_arcface_r100)
    register_model_loader("adaface_vit_kprpe", _load_adaface_vit_kprpe)
    register_model_loader("mobilefacenet", _load_mobilefacenet)
    register_model_loader("dual_embedder", _load_dual_embedder)


register_embedding_loaders()
