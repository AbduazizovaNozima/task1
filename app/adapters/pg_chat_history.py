from datetime import timedelta

from psycopg_pool import ConnectionPool

from app.adapters.pg_connection import connect
from app.domain.models import ChatTurn

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id text PRIMARY KEY,
    topic      text NOT NULL,
    answer_id  uuid,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_updated_at ON chat_sessions (updated_at);
"""

SELECT_ACTIVE = """
SELECT topic, answer_id FROM chat_sessions
WHERE session_id = %s AND updated_at > now() - %s
"""

UPSERT_SESSION = """
INSERT INTO chat_sessions (session_id, topic, answer_id) VALUES (%s, %s, %s)
ON CONFLICT (session_id) DO UPDATE
SET topic = EXCLUDED.topic, answer_id = EXCLUDED.answer_id, updated_at = now()
"""

DELETE_EXPIRED = "DELETE FROM chat_sessions WHERE updated_at < now() - %s"
DELETE_SESSION = "DELETE FROM chat_sessions WHERE session_id = %s"


class PostgresChatHistory:
    def __init__(self, pool: ConnectionPool, ttl: timedelta) -> None:
        self._pool = pool
        self._ttl = ttl

    def create_schema(self) -> None:
        with connect(self._pool) as connection:
            connection.execute(SCHEMA)

    def last(self, session_id: str) -> ChatTurn | None:
        with connect(self._pool) as connection:
            row = connection.execute(SELECT_ACTIVE, (session_id, self._ttl)).fetchone()
        if row is None:
            return None
        topic, answer_id = row
        return ChatTurn(topic=topic, answer_id=answer_id)

    def save(self, session_id: str, turn: ChatTurn) -> None:
        with connect(self._pool) as connection:
            connection.execute(UPSERT_SESSION, (session_id, turn.topic, turn.answer_id))
            connection.execute(DELETE_EXPIRED, (self._ttl,))

    def clear(self, session_id: str) -> None:
        with connect(self._pool) as connection:
            connection.execute(DELETE_SESSION, (session_id,))
