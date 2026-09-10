from t2s.db import ColumnInfo, ForeignKey

PARAM_TYPES: frozenset[str] = frozenset({"varchar", "char", "decimal"})
VERBATIM_TYPES: frozenset[str] = frozenset({"enum", "set"})

HEADER: str = "# schema: sakila (MySQL 8.4)"


def short_type(column_type: str) -> str:
    base = column_type.split("(")[0].split(" ")[0].lower()

    if base in VERBATIM_TYPES:
        return base.upper() + column_type[len(base):]

    if base in PARAM_TYPES and "(" in column_type:
        return base.upper() + column_type[column_type.index("("):column_type.index(")") + 1]

    return base.upper()


def render_schema(
    columns: tuple[ColumnInfo, ...],
    foreign_keys: tuple[ForeignKey, ...],
    include_views: bool = False,
) -> str:
    fk_by_column: dict[tuple[str, str], tuple[str, str]] = {}
    for fk in foreign_keys:
        key = (fk.table_name, fk.column_name)
        if key not in fk_by_column:
            fk_by_column[key] = (fk.referenced_table, fk.referenced_column)

    tables: dict[str, tuple[str, list[str]]] = {}
    for column in columns:
        if not include_views and column.table_type == "VIEW":
            continue
        if column.table_name not in tables:
            tables[column.table_name] = (column.table_type, [])

        part = f"{column.column_name} {short_type(column.column_type)}"
        if column.column_key == "PRI":
            part += " PK"
        if (column.table_name, column.column_name) in fk_by_column:
            ref_table, ref_column = fk_by_column[(column.table_name, column.column_name)]
            part += f" -> {ref_table}.{ref_column}"
        tables[column.table_name][1].append(part)

    lines = [HEADER]
    for table_name, (table_type, parts) in tables.items():
        kind = "VIEW" if table_type == "VIEW" else "TABLE"
        lines.append(f"{kind} {table_name}({', '.join(parts)})")

    return "\n".join(lines)