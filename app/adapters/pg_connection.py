from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, OperationalError
from psycopg_pool import ConnectionPool, PoolTimeout

from app.domain.errors import StorageUnavailableError


@contextmanager
def connect(pool: ConnectionPool) -> Iterator[Connection[tuple[object, ...]]]:
    try:
        with pool.connection() as connection:
            yield connection
    except (PoolTimeout, OperationalError) as exc:
        raise StorageUnavailableError("PostgreSQL bilan aloqa yo'q.") from exc
