from collections.abc import Sequence
from uuid import UUID

from psycopg_pool import ConnectionPool

from app.adapters.pg_connection import connect
from app.domain.models import Answer, QARecord, Question

SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    id   uuid PRIMARY KEY,
    text text NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
    id        uuid PRIMARY KEY,
    answer_id uuid NOT NULL REFERENCES answers (id),
    text      text NOT NULL
);
"""

UPSERT_ANSWER = """
INSERT INTO answers (id, text) VALUES (%s, %s)
ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text
"""

UPSERT_QUESTION = """
INSERT INTO questions (id, answer_id, text) VALUES (%s, %s, %s)
ON CONFLICT (id) DO UPDATE SET answer_id = EXCLUDED.answer_id, text = EXCLUDED.text
"""

SELECT_RECORDS = """
SELECT q.id, q.text, a.text
FROM questions q JOIN answers a ON a.id = q.answer_id
WHERE q.id = ANY(%s)
"""


class PostgresRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def ping(self) -> None:
        with connect(self._pool) as connection:
            connection.execute("SELECT 1")

    def create_schema(self) -> None:
        with connect(self._pool) as connection:
            connection.execute(SCHEMA)

    def upsert(self, answers: Sequence[Answer], questions: Sequence[Question]) -> None:
        with connect(self._pool) as connection, connection.cursor() as cursor:
            cursor.executemany(UPSERT_ANSWER, [(a.id, a.text) for a in answers])
            cursor.executemany(UPSERT_QUESTION, [(q.id, q.answer_id, q.text) for q in questions])

    def get_many(self, question_ids: Sequence[UUID]) -> dict[UUID, QARecord]:
        with connect(self._pool) as connection:
            rows = connection.execute(SELECT_RECORDS, (list(question_ids),)).fetchall()
        return {question_id: QARecord(question=question, answer=answer) for question_id, question, answer in rows}
