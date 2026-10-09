from collections.abc import Sequence
from uuid import UUID

from app.domain.errors import DataInconsistencyError, EmptyQueryError
from app.domain.models import SearchResult, VectorHit
from app.domain.ports import Embedder, QARepository, VectorIndex
from app.domain.text import normalize


class SearchService:
    def __init__(
        self,
        embedder: Embedder,
        index: VectorIndex,
        repository: QARepository,
        threshold: float,
        candidates: int,
    ) -> None:
        self._embedder = embedder
        self._index = index
        self._repository = repository
        self._threshold = threshold
        self._candidates = candidates

    def rank(self, query: str) -> list[VectorHit]:
        text = normalize(query)
        if not text:
            raise EmptyQueryError("Savol matni bo'sh.")
        [vector] = self._embedder.embed([text])
        return best_per_answer(self._index.search(vector, self._candidates))

    def ask(self, query: str) -> SearchResult:
        ranked = self.rank(query)
        if not ranked:
            return SearchResult(found=False, score=None)
        best = ranked[0]
        if best.score < self._threshold:
            return SearchResult(found=False, score=best.score)
        record = self._repository.get(best.question_id)
        if record is None:
            raise DataInconsistencyError(f"Question {best.question_id} is indexed but missing in the database")
        return SearchResult(
            found=True,
            score=best.score,
            answer=record.answer,
            matched_question=record.question,
        )


def best_per_answer(hits: Sequence[VectorHit]) -> list[VectorHit]:
    best: dict[UUID, VectorHit] = {}
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        best.setdefault(hit.answer_id, hit)
    return list(best.values())
