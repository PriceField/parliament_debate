"""LangGraph StateGraph definition and DebateState schema."""

import operator
from typing import Annotated, TypedDict, TYPE_CHECKING

from langgraph.graph import StateGraph, END

from nodes import (
    make_chair_open_node,
    increment_round_node,
    make_supporters_node,
    make_opponents_node,
    make_third_party_node,
    make_supporters_respond_node,
    make_opponents_respond_node,
    make_chair_summary_node,
    make_write_output_node,
)

if TYPE_CHECKING:
    from config import DebateConfig


# ─── State ────────────────────────────────────────────────────────────────────

class DebateState(TypedDict):
    topic: str
    topic_context: str
    round: int
    max_rounds: int
    role_map: dict          # {role_zh: model_key}
    rng_seed: int           # seeded per-debate; each round uses seed+round
    # append-only: each node returns only new records; operator.add merges them
    history: Annotated[list[dict], operator.add]
    # Chair's past summaries for cross-round memory
    chair_summaries: Annotated[list[str], operator.add]
    # Structured claim tracking maintained by the Chair
    claim_registry: str
    # Short title for output folder naming (set by chair opening)
    short_title: str
    # Chair's recommended specialist for next round
    next_specialist: str
    # per-round communication fields
    chair_directive: str
    supporters_speech: str
    opponents_speech: str
    third_party_speech: str
    # Response phase: supporters/opponents respond to specialist intervention
    supporters_response: str
    opponents_response: str
    chair_summary: str
    should_continue: bool


# ─── Routing ─────────────────────────────────────────────────────────────────

def _route_after_summary(state: DebateState) -> str:
    if state["should_continue"] and state["round"] < state["max_rounds"]:
        return "continue_debate"
    return "end_debate"


# ─── Graph Builder ────────────────────────────────────────────────────────────

NODE_CHAIR_OPEN = "chair_open"
NODE_INCREMENT = "increment_round"
NODE_SUPPORTERS = "supporters"
NODE_OPPONENTS = "opponents"
NODE_THIRD_PARTY = "third_party"
NODE_SUPPORTERS_RESPOND = "supporters_respond"
NODE_OPPONENTS_RESPOND = "opponents_respond"
NODE_CHAIR_SUMMARY = "chair_summary"
NODE_WRITE_OUTPUT = "write_output"


def build_debate_graph(models: dict, prompts: dict, cfg: "DebateConfig"):
    """
    Build and compile the debate StateGraph with SQLite checkpointing.
    Checkpointing ensures any interrupted debate can be resumed.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string(cfg.checkpoint_db)
    except Exception as e:
        print(f"[WARN] Could not initialize SQLite checkpointer: {e}")
        print("[WARN] Running without checkpointing — interruptions cannot be resumed.")
        checkpointer = None

    graph = StateGraph(DebateState)

    # Register nodes
    graph.add_node(NODE_CHAIR_OPEN, make_chair_open_node(models, prompts, cfg))
    graph.add_node(NODE_INCREMENT, increment_round_node)
    graph.add_node(NODE_SUPPORTERS, make_supporters_node(models, prompts, cfg))
    graph.add_node(NODE_OPPONENTS, make_opponents_node(models, prompts, cfg))
    graph.add_node(NODE_THIRD_PARTY, make_third_party_node(models, prompts, cfg))
    graph.add_node(NODE_SUPPORTERS_RESPOND, make_supporters_respond_node(models, prompts, cfg))
    graph.add_node(NODE_OPPONENTS_RESPOND, make_opponents_respond_node(models, prompts, cfg))
    graph.add_node(NODE_CHAIR_SUMMARY, make_chair_summary_node(models, prompts, cfg))
    graph.add_node(NODE_WRITE_OUTPUT, make_write_output_node())

    # Static edges (sequential — no parallel fan-out)
    graph.set_entry_point(NODE_CHAIR_OPEN)
    graph.add_edge(NODE_CHAIR_OPEN, NODE_INCREMENT)
    graph.add_edge(NODE_INCREMENT, NODE_SUPPORTERS)
    graph.add_edge(NODE_SUPPORTERS, NODE_OPPONENTS)
    graph.add_edge(NODE_OPPONENTS, NODE_THIRD_PARTY)
    graph.add_edge(NODE_THIRD_PARTY, NODE_SUPPORTERS_RESPOND)
    graph.add_edge(NODE_SUPPORTERS_RESPOND, NODE_OPPONENTS_RESPOND)
    graph.add_edge(NODE_OPPONENTS_RESPOND, NODE_CHAIR_SUMMARY)

    # Conditional edge: continue loop or terminate
    graph.add_conditional_edges(
        NODE_CHAIR_SUMMARY,
        _route_after_summary,
        {
            "continue_debate": NODE_INCREMENT,
            "end_debate": NODE_WRITE_OUTPUT,
        },
    )

    graph.add_edge(NODE_WRITE_OUTPUT, END)

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
