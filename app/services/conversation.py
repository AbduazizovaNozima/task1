import logging

from app.domain.models import ChatTurn, SearchResult
from app.domain.ports import ChatHistory
from app.domain.query import refers_to_previous
from app.services.search import SearchService

logger = logging.getLogger(__name__)

LOG_TEXT_LIMIT = 100
NO_SESSION = "-"


class ConversationService:
    def __init__(self, search: SearchService, history: ChatHistory) -> None:
        self._search = search
        self._history = history

    def ask(self, question: str, session_id: str | None) -> SearchResult:
        previous = self._history.last(session_id) if session_id else None
        result, topic = self._answer(question, previous)
        if session_id and (result.found or result.suggestions):
            self._history.save(session_id, ChatTurn(topic=topic, answer_id=result.answer_id))
        context = previous.topic if previous and result.context_used else None
        logger.info(trace(session_id or NO_SESSION, question, result, context))
        return result

    def reset(self, session_id: str) -> None:
        self._history.clear(session_id)
        logger.info("session=%s history cleared", session_id)

    def _answer(self, question: str, previous: ChatTurn | None) -> tuple[SearchResult, str]:
        standalone = self._search.ask(question)
        if previous is None or not refers_to_previous(question):
            return standalone, question

        contextual = self._search.ask(f"{previous.topic} {question}", exclude_answer_id=previous.answer_id)
        if contextual.found and (not standalone.found or (contextual.score or 0) >= (standalone.score or 0)):
            return contextual.model_copy(update={"context_used": True}), previous.topic
        return standalone, question


def trace(session_id: str, question: str, result: SearchResult, context: str | None) -> str:
    if result.found:
        verdict = "FOUND"
    elif result.suggestions:
        verdict = "AMBIGUOUS"
    else:
        verdict = "NOT FOUND"
    context_note = f' context="{context}"' if context else ""
    score = f"{result.score:.3f}" if result.score is not None else "-"
    lines = [f'session={session_id} question="{question}"{context_note} -> {verdict} score={score}']
    for position, candidate in enumerate(result.candidates, start=1):
        lines.append(f"  #{position} {candidate.score:.3f} Q: {_short(candidate.question)}")
        lines.append(f"           A: {_short(candidate.answer)}")
    return "\n".join(lines)


def _short(text: str) -> str:
    return text if len(text) <= LOG_TEXT_LIMIT else text[: LOG_TEXT_LIMIT - 1] + "…"
