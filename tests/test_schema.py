import inspect

from t2s.db import ColumnInfo, ForeignKey
from t2s.schema import HEADER, render_schema, short_type


def _column(table_name="t", column_name="c", column_type="int", column_key=""):
    return ColumnInfo(
        table_name=table_name,
        table_type="BASE TABLE",
        column_name=column_name,
        data_type="int",
        column_type=column_type,
        is_nullable=False,
        column_key=column_key,
    )


# 19
def test_short_type_int():
    assert short_type("int") == "INT"


# 20
def test_short_type_int_unsigned():
    assert short_type("int unsigned") == "INT"


# 21
def test_short_type_tinyint_one():
    assert short_type("tinyint(1)") == "TINYINT"


# 22
def test_short_type_smallint_unsigned():
    assert short_type("smallint unsigned") == "SMALLINT"


# 23
def test_short_type_varchar_45():
    assert short_type("varchar(45)") == "VARCHAR(45)"


# 24
def test_short_type_char_20():
    assert short_type("char(20)") == "CHAR(20)"


# 25
def test_short_type_decimal_4_2():
    assert short_type("decimal(4,2)") == "DECIMAL(4,2)"


# 26
def test_short_type_decimal_27_2():
    assert short_type("decimal(27,2)") == "DECIMAL(27,2)"


# 27
def test_short_type_varchar_no_parens():
    assert short_type("varchar") == "VARCHAR"


# 28
def test_short_type_enum_values_verbatim():
    assert short_type("enum('G','PG','PG-13','R','NC-17')") == "ENUM('G','PG','PG-13','R','NC-17')"


# 29
def test_short_type_set_values_with_spaces():
    assert short_type("set('Trailers','Commentaries','Deleted Scenes','Behind the Scenes')") == (
        "SET('Trailers','Commentaries','Deleted Scenes','Behind the Scenes')"
    )


# 30
def test_short_type_plain_types():
    assert short_type("text") == "TEXT"
    assert short_type("timestamp") == "TIMESTAMP"
    assert short_type("datetime") == "DATETIME"
    assert short_type("year") == "YEAR"
    assert short_type("mediumblob") == "MEDIUMBLOB"


# 31
def test_render_schema_empty_columns_header_only():
    assert render_schema((), ()) == "# schema: sakila (MySQL 8.4)"


# 32
def test_render_schema_single_plain_column():
    result = render_schema((_column(),), ())
    assert result == f"{HEADER}\nTABLE t(c INT)"


# 33
def test_render_schema_single_pk_column():
    result = render_schema((_column(column_key="PRI"),), ())
    assert result == f"{HEADER}\nTABLE t(c INT PK)"


# 34
def test_render_schema_single_fk_column():
    fk = ForeignKey(
        table_name="t", column_name="c", referenced_table="other", referenced_column="oid"
    )
    result = render_schema((_column(),), (fk,))
    assert result == f"{HEADER}\nTABLE t(c INT -> other.oid)"


# 35
def test_render_schema_pk_and_fk_pk_first():
    fk = ForeignKey(
        table_name="t", column_name="c", referenced_table="other", referenced_column="oid"
    )
    result = render_schema((_column(column_key="PRI"),), (fk,))
    assert result == f"{HEADER}\nTABLE t(c INT PK -> other.oid)"


# 36
def test_render_schema_nullable_not_in_output():
    column = ColumnInfo(
        table_name="t",
        table_type="BASE TABLE",
        column_name="c",
        data_type="int",
        column_type="int",
        is_nullable=True,
        column_key="",
    )
    result = render_schema((column,), ())
    assert result == f"{HEADER}\nTABLE t(c INT)"


# 37
def test_render_schema_preserves_first_appearance_order():
    table_b = (
        _column(table_name="b"),
        _column(table_name="b", column_name="x"),
    )
    table_a = (_column(table_name="a"),)
    result = render_schema(table_b + table_a, ())
    lines = result.splitlines()
    assert lines[0] == HEADER
    assert lines[1] == "TABLE b(c INT, x INT)"
    assert lines[2] == "TABLE a(c INT)"


# 38
def test_render_schema_view_only_excluded_by_default():
    column = ColumnInfo(
        table_name="v",
        table_type="VIEW",
        column_name="c",
        data_type="int",
        column_type="int",
        is_nullable=False,
        column_key="",
    )
    assert render_schema((column,), ()) == HEADER


# 39
def test_render_schema_view_included_with_include_views():
    column = ColumnInfo(
        table_name="v",
        table_type="VIEW",
        column_name="c",
        data_type="int",
        column_type="int",
        is_nullable=False,
        column_key="",
    )
    result = render_schema((column,), (), include_views=True)
    assert result == f"{HEADER}\nVIEW v(c INT)"


# 40
def test_render_schema_duplicate_fk_key_uses_first():
    first = ForeignKey(
        table_name="t", column_name="c", referenced_table="other", referenced_column="oid"
    )
    second = ForeignKey(
        table_name="t", column_name="c", referenced_table="another", referenced_column="aid"
    )
    result = render_schema((_column(),), (first, second))
    assert result == f"{HEADER}\nTABLE t(c INT -> other.oid)"


# 41
def test_schema_module_imports_only_t2s_db():
    import ast
    import inspect

    import t2s.schema as schema_module

    tree = ast.parse(inspect.getsource(schema_module))
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert sorted(modules) == ["t2s.db"]