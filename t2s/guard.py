import re


class UnsafeSQLError(ValueError):
    ...


MAX_ROWS: int = 200

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "MERGE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "RENAME",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "LOCK",
    "UNLOCK",
    "SET",
    "CALL",
    "EXECUTE",
    "PREPARE",
    "DEALLOCATE",
    "LOAD",
    "INFILE",
    "OUTFILE",
    "DUMPFILE",
    "HANDLER",
    "USE",
    "SHUTDOWN",
    "KILL",
    "FLUSH",
    "INTO",
)

SYSTEM_SCHEMAS: tuple[str, ...] = (
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
)


def _normalize(sql: str) -> tuple[str, str]:
    NORMAL = 0
    SQUOTE = 1
    DQUOTE = 2
    BACKTICK = 3
    LINE_COMMENT = 4
    BLOCK_COMMENT = 5

    state = NORMAL
    stripped: list[str] = []
    masked: list[str] = []
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]
        if state == NORMAL:
            if sql.startswith("/*!", i):
                raise UnsafeSQLError("executable comment is not allowed")
            if sql.startswith("/*", i):
                stripped.append(" ")
                masked.append(" ")
                state = BLOCK_COMMENT
                i += 2
            elif sql.startswith("--", i) and (i + 2 >= n or sql[i + 2].isspace()):
                stripped.append(" ")
                masked.append(" ")
                state = LINE_COMMENT
                i += 2
            elif ch == "#":
                stripped.append(" ")
                masked.append(" ")
                state = LINE_COMMENT
                i += 1
            elif ch == "'":
                stripped.append(ch)
                masked.append(ch)
                state = SQUOTE
                i += 1
            elif ch == '"':
                stripped.append(ch)
                masked.append(ch)
                state = DQUOTE
                i += 1
            elif ch == "`":
                stripped.append(ch)
                masked.append(ch)
                state = BACKTICK
                i += 1
            else:
                stripped.append(ch)
                masked.append(ch)
                i += 1
        elif state == LINE_COMMENT:
            if ch == "\n":
                state = NORMAL
            i += 1
        elif state == BLOCK_COMMENT:
            if sql.startswith("*/", i):
                state = NORMAL
                i += 2
            else:
                i += 1
        elif state in (SQUOTE, DQUOTE):
            quote = "'" if state == SQUOTE else '"'
            if ch == "\\":
                if i + 1 >= n:
                    raise UnsafeSQLError("unterminated string literal")
                stripped.append(sql[i])
                stripped.append(sql[i + 1])
                i += 2
            elif sql.startswith(quote * 2, i):
                stripped.append(sql[i])
                stripped.append(sql[i + 1])
                i += 2
            elif ch == quote:
                stripped.append(ch)
                masked.append(ch)
                state = NORMAL
                i += 1
            else:
                stripped.append(ch)
                i += 1
        elif state == BACKTICK:
            if sql.startswith("``", i):
                stripped.append(sql[i])
                stripped.append(sql[i + 1])
                i += 2
            elif ch == "`":
                stripped.append(ch)
                masked.append(ch)
                state = NORMAL
                i += 1
            else:
                stripped.append(ch)
                i += 1

    if state == BLOCK_COMMENT:
        raise UnsafeSQLError("unterminated block comment")
    if state in (SQUOTE, DQUOTE):
        raise UnsafeSQLError("unterminated string literal")
    if state == BACKTICK:
        raise UnsafeSQLError("unterminated identifier")

    return "".join(stripped), "".join(masked)


def ensure_safe_sql(sql: str, max_rows: int = MAX_ROWS) -> str:
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError(f"max_rows must be >= 1, got: {max_rows}")
    if not isinstance(sql, str):
        raise TypeError(f"sql must be str, got: {type(sql).__name__}")

    stripped, masked = _normalize(sql)

    stripped = re.sub(r"\s+", " ", stripped).strip()
    masked = re.sub(r"\s+", " ", masked).strip()

    if masked.endswith(";"):
        stripped = stripped[:-1].strip()
        masked = masked[:-1].strip()

    if ";" in masked:
        raise UnsafeSQLError("multiple statements are not allowed")
    if masked == "":
        raise UnsafeSQLError("empty SQL")

    token = masked.split()[0].upper()
    if token not in ("SELECT", "WITH"):
        raise UnsafeSQLError(f"only SELECT is allowed, got: {token}")

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", masked, re.IGNORECASE):
            raise UnsafeSQLError(f"forbidden keyword: {kw}")

    for name in SYSTEM_SCHEMAS:
        if re.search(rf"\b{name}\s*\.", masked, re.IGNORECASE):
            raise UnsafeSQLError(f"system schema access is not allowed: {name}")

    if re.search(r"\bLIMIT\b", masked, re.IGNORECASE) is None:
        stripped = f"{stripped} LIMIT {max_rows}"

    return stripped