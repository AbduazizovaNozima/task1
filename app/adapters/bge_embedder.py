import logging
from collections.abc import Sequence
from functools import cached_property

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class BgeEmbedder:
    def __init__(self, model_name: str, revision: str, device: str, batch_size: int, max_length: int) -> None:
        self._model_name = model_name
        self._revision = revision
        self._device = device
        self._batch_size = batch_size
        self._max_length = max_length

    @cached_property
    def _model(self) -> SentenceTransformer:
        logger.info("Loading embedding model %s@%s on %s", self._model_name, self._revision[:8], self._device)
        model = SentenceTransformer(self._model_name, revision=self._revision, device=self._device)
        model.max_seq_length = self._max_length
        return model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result: list[list[float]] = vectors.tolist()
        return result
