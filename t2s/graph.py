from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from t2s.config import Settings
from t2s.db import QueryError, QueryResult, run_query
from t2s.guard import UnsafeSQLError
from t2s.llm import LLMError, generate_sql
from t2s.prompt import Extraction


STATUSES: tuple[str, ...] = (
    "answered",
    "unsupported",
    "unparsable",
    "blocked",
    "db_error",
    "llm_error",
)


class AgentState(TypedDict, total=False):
    question: str
    extraction: Extraction
    result: QueryResult
    status: str
    error: str


@dataclass(frozen=True)
class Answer:
    question: str
    status: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    error: str


def build_graph(
    settings: Settings,
    schema_text: str,
    generate: Callable[[str, str, Settings], Extraction] = generate_sql,
    execute: Callable[[str, Settings], QueryResult] = run_query,
) -> CompiledStateGraph:
    def generate_node(state: AgentState) -> dict:
        try:
            extraction = generate(schema_text, state["question"], settings)
        except LLMError as exc:
            return {"status": "llm_error", "error": str(exc)}
        if extraction.kind != "sql":
            return {"extraction": extraction, "status": extraction.kind}
        return {"extraction": extraction}

    def route(state: AgentState) -> str:
        if "status" in state:
            return END
        return "execute"

    def execute_node(state: AgentState) -> dict:
        try:
            result = execute(state["extraction"].sql, settings)
        except UnsafeSQLError as exc:
            return {"status": "blocked", "error": str(exc)}
        except QueryError as exc:
            return {"status": "db_error", "error": str(exc)}
        return {"result": result, "status": "answered"}

    builder = StateGraph(AgentState)
    builder.add_node("generate", generate_node)
    builder.add_node("execute", execute_node)
    builder.add_edge(START, "generate")
    builder.add_conditional_edges("generate", route, {"execute": "execute", END: END})
    builder.add_edge("execute", END)
    return builder.compile()


def ask(question: str, graph: CompiledStateGraph) -> Answer:
    state = graph.invoke({"question": question})
    extraction = state.get("extraction")
    result = state.get("result")

    if result is not None:
        sql = result.sql
        columns = result.columns
        rows = result.rows
    elif extraction is not None:
        sql = extraction.sql
        columns = ()
        rows = ()
    else:
        sql = ""
        columns = ()
        rows = ()

    return Answer(
        question=question,
        status=state["status"],
        sql=sql,
        columns=columns,
        rows=rows,
        error=state.get("error", ""),
    )