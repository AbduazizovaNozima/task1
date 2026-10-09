import logging
from collections.abc import Sequence
from itertools import batched
from uuid import UUID

from app.domain.models import Answer, IngestReport, QAPair, QASheet, Question
from app.domain.ports import Embedder, QARepository, VectorIndex
from app.domain.text import normalize, stable_id

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        repository: QARepository,
        index: VectorIndex,
        embedder: Embedder,
        batch_size: int,
    ) -> None:
        self._repository = repository
        self._index = index
        self._embedder = embedder
        self._batch_size = batch_size

    def ingest(self, sheet: QASheet) -> IngestReport:
        answers, questions = to_records(sheet.pairs)
        self._repository.upsert(answers, questions)
        newly_indexed = self._index_changed(questions)
        report = IngestReport(
            rows_read=len(sheet.pairs) + len(sheet.skipped),
            rows_skipped=len(sheet.skipped),
            answers=len(answers),
            questions=len(questions),
            newly_indexed=newly_indexed,
        )
        logger.info("Ingestion finished: %s", report.model_dump())
        return report

    def _index_changed(self, questions: Sequence[Question]) -> int:
        indexed = self._index.indexed_answer_ids([q.id for q in questions])
        changed = [q for q in questions if indexed.get(q.id) != q.answer_id]
        done = 0
        for batch in batched(changed, self._batch_size):
            vectors = self._embedder.embed([normalize(q.text) for q in batch])
            self._index.upsert(batch, vectors)
            done += len(batch)
            logger.info("Indexed %d/%d questions", done, len(changed))
        return len(changed)


def to_records(pairs: Sequence[QAPair]) -> tuple[list[Answer], list[Question]]:
    answers: dict[UUID, Answer] = {}
    questions: dict[UUID, Question] = {}
    for pair in pairs:
        answer = Answer(id=stable_id(pair.answer), text=pair.answer)
        answers.setdefault(answer.id, answer)
        question = Question(id=stable_id(pair.question), answer_id=answer.id, text=pair.question)
        previous = questions.get(question.id)
        if previous is not None and previous.answer_id != question.answer_id:
            logger.warning("Question %r has several answers; the last one is kept", pair.question)
        questions[question.id] = question
    return list(answers.values()), list(questions.values())
