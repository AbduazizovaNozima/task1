from collections.abc import Sequence
from uuid import UUID

from app.domain.errors import EmptyQueryError
from app.domain.models import Candidate, SearchResult, VectorHit
from app.domain.ports import Embedder, QARepository, VectorIndex
from app.domain.query import expand, word_count
from app.domain.text import stable_id


class SearchService:
    def __init__(
        self,
        embedder: Embedder,
        index: VectorIndex,
        repository: QARepository,
        threshold: float,
        candidates: int,
        top_k: int,
        ambiguity_margin: float,
        ambiguity_max_words: int,
    ) -> None:
        self._embedder = embedder
        self._index = index
        self._repository = repository
        self._threshold = threshold
        self._candidates = candidates
        self._top_k = top_k
        self._ambiguity_margin = ambiguity_margin
        self._ambiguity_max_words = ambiguity_max_words

    def rank(self, query: str) -> list[VectorHit]:
        text = expand(query)
        if not text:
            raise EmptyQueryError("Savol matni bo'sh.")
        [vector] = self._embedder.embed([text])
        hits = self._index.search(vector, self._candidates)
        records = self._repository.get_many([hit.question_id for hit in hits])
        # SQL is the publication boundary. Partial vector writes may survive a rollback.
        committed = [
            hit.model_copy(update={"answer_id": stable_id(records[hit.question_id].answer)})
            for hit in hits
            if hit.question_id in records
        ]
        return best_per_answer(committed)

    def ask(self, query: str) -> SearchResult:
        hits = self.rank(query)[: self._top_k]
        return self._decide(query, self._candidates_for(hits))

    def _candidates_for(self, hits: list[VectorHit]) -> list[Candidate]:
        records = self._repository.get_many([hit.question_id for hit in hits])
        return [
            Candidate(
                answer_id=stable_id(records[hit.question_id].answer),
                question=records[hit.question_id].question,
                answer=records[hit.question_id].answer,
                score=hit.score,
            )
            for hit in hits
            if hit.question_id in records
        ]

    def _decide(self, query: str, candidates: list[Candidate]) -> SearchResult:
        if not candidates:
            return SearchResult(found=False, score=None)
        best = candidates[0]
        if best.score < self._threshold:
            return SearchResult(found=False, score=best.score)
        if self._is_ambiguous(query, candidates):
            close = [c.question for c in candidates if best.score - c.score < self._ambiguity_margin]
            return SearchResult(found=False, score=best.score, suggestions=close)
        return SearchResult(
            found=True,
            score=best.score,
            answer_id=best.answer_id,
            answer=best.answer,
            matched_question=best.question,
        )

    def _is_ambiguous(self, query: str, candidates: list[Candidate]) -> bool:
        if len(candidates) < 2 or word_count(query) > self._ambiguity_max_words:
            return False
        return candidates[0].score - candidates[1].score < self._ambiguity_margin


def best_per_answer(hits: Sequence[VectorHit]) -> list[VectorHit]:
    best: dict[UUID, VectorHit] = {}
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        best.setdefault(hit.answer_id, hit)
    return list(best.values())
