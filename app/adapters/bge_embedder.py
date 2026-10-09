import logging
from collections.abc import Sequence

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class BgeEmbedder:
    def __init__(self, model_name: str, device: str, batch_size: int, max_length: int) -> None:
        logger.info("Loading embedding model %s on %s", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._model.max_seq_length = max_length
        self._batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result: list[list[float]] = vectors.tolist()
        return result
