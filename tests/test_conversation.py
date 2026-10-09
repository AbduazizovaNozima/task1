import logging

import pytest

from app.domain.models import QAPair
from tests.fakes import Services, build_services

PAIRS = [
    QAPair(question="pasport olish hujjatlar", answer="Ariza va tug'ilganlik guvohnomasi."),
    QAPair(question="pasport olish muddati", answer="1 ish kuni."),
    QAPair(question="pasport olish joyi", answer="Davlat xizmatlari markazi."),
    QAPair(question="nikoh qayd etish", answer="FHDYO bo'limida."),
]
SESSION = "telegram-1-1"


@pytest.fixture
def services() -> Services:
    return build_services(PAIRS)


def test_follow_up_uses_topic_of_previous_question(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)

    result = services.conversation.ask("muddati chi?", SESSION)

    assert result.context_used
    assert result.answer == "1 ish kuni."


def test_follow_up_never_repeats_previous_answer(services: Services) -> None:
    first = services.conversation.ask("pasport olish hujjatlar", SESSION)

    second = services.conversation.ask("buning joyi qayerda", SESSION)

    assert second.context_used
    assert second.answer_id != first.answer_id


def test_follow_ups_stay_anchored_to_topic(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)
    services.conversation.ask("muddati chi?", SESSION)

    services.conversation.ask("joyi chi?", SESSION)

    turn = services.history.last(SESSION)
    assert turn is not None
    assert turn.topic == "pasport olish"


def test_new_question_with_its_own_answer_ignores_previous_topic(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)

    result = services.conversation.ask("nikoh qayd", SESSION)

    assert result.answer == "FHDYO bo'limida."
    assert not result.context_used


def test_not_found_question_does_not_replace_topic(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)
    services.conversation.ask("bugungi futbol natijasi", SESSION)

    assert services.conversation.ask("muddati chi?", SESSION).context_used


def test_short_unrelated_message_is_not_glued_to_topic(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)

    assert not services.conversation.ask("men haydovchi", SESSION).context_used


def test_users_have_separate_histories(services: Services) -> None:
    services.conversation.ask("pasport olish", "telegram-1-1")

    result = services.conversation.ask("muddati chi?", "telegram-1-2")

    assert not result.context_used


def test_reset_forgets_history(services: Services) -> None:
    services.conversation.ask("pasport olish", SESSION)

    services.conversation.reset(SESSION)

    assert services.history.last(SESSION) is None
    assert not services.conversation.ask("muddati chi?", SESSION).context_used


def test_without_session_nothing_is_stored(services: Services) -> None:
    services.conversation.ask("pasport olish hujjatlar", None)

    assert services.history.sessions == {}


def test_each_question_is_logged_once_with_top_candidates(services: Services, caplog: pytest.LogCaptureFixture) -> None:
    services.conversation.ask("pasport olish", SESSION)
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="app.services.conversation"):
        services.conversation.ask("muddati chi?", SESSION)

    [message] = caplog.messages
    assert message.startswith(f'session={SESSION} question="muddati chi?" context="pasport olish" -> FOUND')
    assert "#1" in message and "Q: pasport olish muddati" in message and "A: 1 ish kuni." in message
