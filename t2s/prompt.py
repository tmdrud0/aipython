import json
import re
from dataclasses import dataclass


SYSTEM_PROMPT: str = """You are a MySQL 8.4 query writer for the `sakila` database.

Output format (strict):
- Reply with ONE fenced code block and nothing else:
```sql
<the query>
```
- No prose before or after the block. No trailing semicolon.
- If the request cannot be answered with a SELECT over the given schema, reply with exactly:
```sql
UNSUPPORTED
```

Query rules:
- Only SELECT (or WITH ... SELECT). Never INSERT/UPDATE/DELETE/DROP/ALTER/GRANT.
- Use only tables and columns present in the schema. Never invent names.
- Never reference information_schema, mysql, performance_schema or sys.
- Add LIMIT (at most 200) unless the query returns a single aggregate row.
- Use explicit JOIN ... ON, never comma joins."""

THINK_END: str = "</think>"
UNSUPPORTED: str = "UNSUPPORTED"
EXTRACTION_KINDS: tuple[str, ...] = ("sql", "unsupported", "unparsable")

FENCE = re.compile(r"```[ \t]*([A-Za-z]*)[ \t]*\r?\n(.*?)```", re.DOTALL)
SQL_START = re.compile(r"\b(?:SELECT|WITH)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Extraction:
    sql: str
    kind: str


def build_messages(schema_text: str, question: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{schema_text}\n\nQuestion: {question}"},
    ]


def _from_sql_text(body: str, *, whole: bool) -> Extraction | None:
    body = body.strip()
    if body == "":
        return None

    starts = [m.start() for m in SQL_START.finditer(body)]
    if not starts:
        if UNSUPPORTED in body.upper():
            return Extraction(sql="", kind="unsupported")
        return None

    if whole:
        sql = body
    else:
        sql = body[starts[-1]:].strip()
        sql = sql.split("\n\n")[0].strip()

    sql = sql.rstrip(";").strip()
    if sql == "" or SQL_START.match(sql) is None:
        return None

    return Extraction(sql=sql, kind="sql")


def extract_sql(text: str) -> Extraction:
    if THINK_END in text:
        text = text.split(THINK_END)[-1]
    text = text.strip()

    blocks = [(lang.lower(), body.strip()) for lang, body in FENCE.findall(text)]

    json_candidates = [body for lang, body in blocks if lang == "json"] + [text]
    for candidate in json_candidates:
        if not candidate.lstrip().startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("sql"), str):
            inner = payload["sql"].strip()
            if inner == "" or inner.upper() == UNSUPPORTED:
                return Extraction(sql="", kind="unsupported")
            result = _from_sql_text(inner, whole=True)
            if result is None:
                return Extraction(sql="", kind="unparsable")
            return result

    for lang, body in blocks:
        if lang == "sql" or lang == "":
            result = _from_sql_text(body, whole=True)
            if result is not None:
                return result

    result = _from_sql_text(text, whole=False)
    if result is None:
        return Extraction(sql="", kind="unparsable")
    return result