from dataclasses import dataclass

import pymysql
import pymysql.err

from t2s.config import Settings
from t2s.guard import MAX_ROWS, ensure_safe_sql


class QueryError(RuntimeError):
    ...


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    sql: str


@dataclass(frozen=True)
class ColumnInfo:
    table_name: str
    table_type: str
    column_name: str
    data_type: str
    is_nullable: bool
    column_key: str


SCHEMA_SQL: str = (
    "SELECT c.TABLE_NAME, t.TABLE_TYPE, c.COLUMN_NAME, "
    "c.DATA_TYPE, c.IS_NULLABLE, c.COLUMN_KEY "
    "FROM information_schema.COLUMNS AS c "
    "JOIN information_schema.TABLES AS t "
    "ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME "
    "WHERE c.TABLE_SCHEMA = %s "
    "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION"
)


def connect(settings: Settings) -> pymysql.connections.Connection:
    try:
        connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            connect_timeout=3,
        )
    except pymysql.err.OperationalError as exc:
        raise QueryError(
            f"cannot connect to {settings.db_host}:{settings.db_port}: {exc.args[1]}"
        ) from exc
    return connection


def run_query(sql: str, settings: Settings, max_rows: int = MAX_ROWS) -> QueryResult:
    safe_sql = ensure_safe_sql(sql, max_rows=max_rows)

    connection = connect(settings)
    try:
        with connection.cursor() as cursor:
            try:
                cursor.execute(safe_sql)
            except (
                pymysql.err.OperationalError,
                pymysql.err.ProgrammingError,
                pymysql.err.InternalError,
                pymysql.err.DataError,
            ) as exc:
                raise QueryError(f"query failed [{exc.args[0]}]: {exc.args[1]}") from exc

            if cursor.description is None:
                columns = ()
            else:
                columns = tuple(d[0] for d in cursor.description)
            rows = tuple(cursor.fetchmany(max_rows))
    finally:
        connection.close()

    return QueryResult(columns=columns, rows=rows, sql=safe_sql)


def fetch_schema(settings: Settings) -> tuple[ColumnInfo, ...]:
    connection = connect(settings)
    try:
        with connection.cursor() as cursor:
            try:
                cursor.execute(SCHEMA_SQL, (settings.db_name,))
            except (
                pymysql.err.OperationalError,
                pymysql.err.ProgrammingError,
                pymysql.err.InternalError,
                pymysql.err.DataError,
            ) as exc:
                raise QueryError(f"query failed [{exc.args[0]}]: {exc.args[1]}") from exc

            rows = cursor.fetchall()
    finally:
        connection.close()

    return tuple(
        ColumnInfo(
            table_name=row[0],
            table_type=row[1],
            column_name=row[2],
            data_type=row[3],
            is_nullable=row[4] == "YES",
            column_key=row[5],
        )
        for row in rows
    )