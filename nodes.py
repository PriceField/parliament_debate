"""LangGraph node factory functions for the debate system."""

import re
from datetime import datetime
from typing import Callable, TYPE_CHECKING

from models import call_model
from assignment import pick_specialist_for_round
from output import generate_raw_filepath

if TYPE_CHECKING:
    from config import DebateConfig

CONTINUE_SIGNAL = "CONTINUE DEBATE"
CONCLUDE_SIGNAL = "CONCLUDE DEBATE"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_record(round_num: int, role: str, model_key: str, content: str) -> dict:
    return {
        "round": round_num,
        "role_zh": role,
        "model_name": model_key,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }


def _append_raw(state: dict, role: str, model_key: str, text: str) -> None:
    """Append a raw speech block to the incremental output file. Never raises."""
    path = state.get("raw_output_path")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {role} [{model_key}] R{state.get('round', '?')} ---\n")
            f.write(text)
            f.write("\n")
    except Exception as e:
        print(f"[WARN] Could not append to raw output: {e}")


def _build_context(state: dict, current_role: str, cfg: "DebateConfig") -> str:
    """
    Build a trimmed debate history for injection into a model's user message.
    - Last N rounds: full content
    - Earlier rounds: digest per speech
    """
    history = state.get("history", [])
    if not history:
        return "This is the first speech of the debate."

    sections = []

    # Opening speech (round 0) always included as digest
    opening_records = [r for r in history if r["round"] == 0]
    if opening_records:
        digest = opening_records[0]["content"][:cfg.opening_digest_chars].replace("\n", " ")
        sections.append(f"CHAIR'S OPENING (digest): {digest}...")

    rounds_in_history = sorted(set(r["round"] for r in history if r["round"] > 0))
    full_detail_rounds = rounds_in_history[-cfg.full_detail_rounds:]  # last N rounds verbatim
    summary_rounds = rounds_in_history[:-cfg.full_detail_rounds]      # earlier rounds as digest

    if summary_rounds:
        sections.append(
            f"\nEARLIER ROUNDS DIGEST (Rounds {summary_rounds[0]}–{summary_rounds[-1]}):"
        )
        for r_num in summary_rounds:
            for speech in [r for r in history if r["round"] == r_num]:
                digest = speech["content"][:cfg.summary_digest_chars].replace("\n", " ")
                sections.append(f"  [{speech['role_zh']}]: {digest}...")

    for r_num in full_detail_rounds:
        sections.append(f"\n--- ROUND {r_num} (FULL) ---")
        for speech in [r for r in history if r["round"] == r_num]:
            sections.append(
                f"\n{speech['role_zh']} [{speech['model_name']}]:\n{speech['content']}"
            )

    context = "\n".join(sections)

    # Hard truncation as last resort
    if len(context) > cfg.max_history_chars:
        context = context[:cfg.max_history_chars]
        context += "\n[... HISTORY TRUNCATED DUE TO LENGTH ...]"

    return context


def _extract_short_title(chair_text: str, fallback_topic: str) -> str:
    """Extract [SHORT_TITLE: ...] from chair's opening. Falls back to truncated topic."""
    match = re.search(r'\[SHORT_TITLE:\s*(.+?)\]', chair_text)
    if match:
        title = match.group(1).strip()
        # Clean for filesystem safety
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        return title
    # Fallback: truncate topic
    safe = re.sub(r'[<>:"/\\|?*\s]', '_', fallback_topic)
    return safe[:15]


def _extract_specialist_recommendation(chair_text: str) -> str:
    """Extract [SPECIALIST: role] from chair's output. Returns empty string if not found."""
    match = re.search(r'\[SPECIALIST:\s*(.+?)\]', chair_text)
    if match:
        return match.group(1).strip()
    return ""


def _header(state: dict) -> str:
    """Common topic/round opening block shared by the five debate nodes."""
    topic_ctx = state.get("topic_context") or "None provided."
    return (
        f"DEBATE TOPIC: {state['topic']}\n"
        f"TOPIC CONTEXT: {topic_ctx}\n"
        f"CURRENT ROUND: {state['round']} of {state['max_rounds']}"
    )


def _extract_claim_registry(chair_text: str, previous_registry: str) -> str:
    """Extract CLAIM REGISTRY section from chair's output. Falls back to previous registry."""
    match = re.search(r'CLAIM REGISTRY:\s*\n((?:- \[.*\n?)*)', chair_text, re.IGNORECASE)
    if match:
        return "CLAIM REGISTRY:\n" + match.group(1).strip()
    return previous_registry


def parse_chair_decision(chair_text: str) -> bool:
    """Returns True if debate should continue."""
    # Try structured [DECISION: ...] tag first (most reliable)
    match = re.search(r'\[DECISION:\s*(CONTINUE|CONCLUDE)\]', chair_text, re.IGNORECASE)
    if match:
        return match.group(1).upper() == "CONTINUE"

    # Fallback to legacy phrase matching
    upper = chair_text.upper()
    if CONCLUDE_SIGNAL in upper:
        return False
    if CONTINUE_SIGNAL in upper:
        return True
    print(f"[WARN] Chair did not output explicit decision signal. Defaulting to CONTINUE.")
    return True


# ─── Node Factories ───────────────────────────────────────────────────────────

def make_chair_open_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def chair_open_node(state: dict) -> dict:
        first_specialist = pick_specialist_for_round(state["rng_seed"], 1)
        system = prompts["chair_open"]
        topic_ctx = state.get("topic_context") or "None provided."
        user = f"""DEBATE TOPIC: {state['topic']}
TOPIC CONTEXT: {topic_ctx}
TOTAL PLANNED ROUNDS: {state['max_rounds']}
SPECIALIST ROLE FOR ROUND 1: {first_specialist}

Please deliver the opening statement.
Include:
(1) A precise framing of what is actually at stake
(2) The single most contested assumption in this debate
(3) A specific directive/question for the debaters to address in Round 1
(4) Announcement of the specialist role that will intervene this round
"""
        chair_model = state["role_map"]["chair"]
        speech = call_model(models, chair_model, system, user, cfg)

        short_title = _extract_short_title(speech, state["topic"])
        raw_path = generate_raw_filepath(short_title, cfg)

        # Write raw file header
        try:
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(f"TOPIC: {state['topic']}\n")
                f.write(f"SEED: {state['rng_seed']}\n")
                f.write(f"STARTED: {datetime.now().isoformat()}\n")
        except Exception as e:
            print(f"[WARN] Could not create raw output file: {e}")
            raw_path = ""

        print(f"\n[Chair - {chair_model}] Opening:\n{speech}\n")
        # Build a temporary state with raw_output_path so _append_raw can use it
        tmp_state = {**state, "raw_output_path": raw_path, "round": 0}
        _append_raw(tmp_state, "chair", chair_model, speech)

        if raw_path:
            print(f"[INFO] Raw output: {raw_path}")
        print(f"[INFO] Short title: {short_title}")

        record = _make_record(0, "chair", chair_model, speech)
        return {
            "chair_directive": speech,
            "short_title": short_title,
            "raw_output_path": raw_path,
            "history": [record],
        }
    return chair_open_node


def increment_round_node(state: dict) -> dict:
    """Pure state operation: advance round counter and reset per-round fields."""
    new_round = state["round"] + 1
    print(f"\n{'='*60}")
    print(f"  ROUND {new_round} / {state['max_rounds']}")
    print(f"{'='*60}")
    return {
        "round": new_round,
        "supporters_speech": "",
        "opponents_speech": "",
        "third_party_speech": "",
        "supporters_response": "",
        "opponents_response": "",
        "chair_summary": "",
    }


def make_supporters_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def supporters_node(state: dict) -> dict:
        model_key = state["role_map"]["supporters"]

        # Get previous round opponents speech for rebuttal (if any)
        prev_opp = ""
        if state["round"] > 1:
            prev_opps = [
                r for r in state["history"]
                if r["round"] == state["round"] - 1 and r["role_zh"] == "opponents"
            ]
            if prev_opps:
                prev_opp = prev_opps[-1]["content"]

        context = _build_context(state, "supporters", cfg)
        system = prompts["supporters"]
        user = f"""{_header(state)}

CHAIR'S DIRECTIVE FOR THIS ROUND:
{state['chair_directive']}

OPPONENTS' PREVIOUS ARGUMENT (rebut this if Round > 1):
{prev_opp or 'N/A — this is Round 1.'}

{state.get('claim_registry') or ''}

DEBATE HISTORY:
{context}

Deliver your speech as Supporters. Reference claim IDs (e.g. [OPP-1]) when responding to tracked claims.
"""
        speech = call_model(models, model_key, system, user, cfg)
        print(f"\n  [Supporters - {model_key}]\n{speech}\n")
        _append_raw(state, "supporters", model_key, speech)

        record = _make_record(state["round"], "supporters", model_key, speech)
        return {
            "supporters_speech": speech,
            "history": [record],
        }
    return supporters_node


def make_opponents_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def opponents_node(state: dict) -> dict:
        model_key = state["role_map"]["opponents"]

        context = _build_context(state, "opponents", cfg)
        system = prompts["opponents"]
        user = f"""{_header(state)}

CHAIR'S DIRECTIVE FOR THIS ROUND:
{state['chair_directive']}

SUPPORTERS' SPEECH THIS ROUND (respond to this directly):
{state['supporters_speech']}

{state.get('claim_registry') or ''}

DEBATE HISTORY:
{context}

Deliver your speech as Opponents. Reference claim IDs (e.g. [SUP-1]) when responding to tracked claims.
"""
        speech = call_model(models, model_key, system, user, cfg)
        print(f"\n  [Opponents - {model_key}]\n{speech}\n")
        _append_raw(state, "opponents", model_key, speech)

        record = _make_record(state["round"], "opponents", model_key, speech)
        return {
            "opponents_speech": speech,
            "history": [record],
        }
    return opponents_node


def make_third_party_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def third_party_node(state: dict) -> dict:
        # Use chair's recommendation if available and valid, otherwise seeded random
        recommended = state.get("next_specialist", "")
        if recommended and recommended in state["role_map"] and recommended in prompts:
            role = recommended
            print(f"  [INFO] Using chair-recommended specialist: {role}")
        else:
            role = pick_specialist_for_round(state["rng_seed"], state["round"])
        model_key = state["role_map"][role]

        context = _build_context(state, role, cfg)
        system = prompts[role]
        user = f"""{_header(state)}

SUPPORTERS said (this round):
{state['supporters_speech']}

OPPONENTS said (this round):
{state['opponents_speech']}

{state.get('claim_registry') or ''}

DEBATE HISTORY:
{context}

Deliver your intervention as {role}. Reference claim IDs (e.g. [SUP-1], [OPP-1]) when addressing tracked claims.
"""
        speech = call_model(models, model_key, system, user, cfg)
        print(f"\n  [{role} - {model_key}]\n{speech}\n")
        _append_raw(state, role, model_key, speech)

        record = _make_record(state["round"], role, model_key, speech)
        return {
            "third_party_speech": speech,
            "history": [record],
        }
    return third_party_node


def make_supporters_respond_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def supporters_respond_node(state: dict) -> dict:
        model_key = state["role_map"]["supporters"]
        system = prompts["supporters_respond"]
        user = f"""{_header(state)}

CHAIR'S DIRECTIVE FOR THIS ROUND:
{state['chair_directive']}

YOUR MAIN SPEECH THIS ROUND (for reference):
{state['supporters_speech'][:400]}

SPECIALIST INTERVENTION (respond to THIS):
{state['third_party_speech']}

Respond directly to the specialist's specific intervention. Do NOT re-argue your general position. 100-150 words.
"""
        speech = call_model(models, model_key, system, user, cfg)
        print(f"\n  [Supporters' Response - {model_key}]\n{speech}\n")
        _append_raw(state, "supporters_response", model_key, speech)

        record = _make_record(state["round"], "supporters_response_key", model_key, speech)
        return {
            "supporters_response": speech,
            "history": [record],
        }
    return supporters_respond_node


def make_opponents_respond_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def opponents_respond_node(state: dict) -> dict:
        model_key = state["role_map"]["opponents"]
        system = prompts["opponents_respond"]
        user = f"""{_header(state)}

CHAIR'S DIRECTIVE FOR THIS ROUND:
{state['chair_directive']}

YOUR MAIN SPEECH THIS ROUND (for reference):
{state['opponents_speech'][:400]}

SPECIALIST INTERVENTION:
{state['third_party_speech']}

SUPPORTERS' RESPONSE TO THE INTERVENTION (critique this too):
{state['supporters_response']}

Respond to the specialist's intervention AND critique the Supporters' response. 100-150 words.
"""
        speech = call_model(models, model_key, system, user, cfg)
        print(f"\n  [Opponents' Response - {model_key}]\n{speech}\n")
        _append_raw(state, "opponents_response", model_key, speech)

        record = _make_record(state["round"], "opponents_response_key", model_key, speech)
        return {
            "opponents_response": speech,
            "history": [record],
        }
    return opponents_respond_node


def make_chair_summary_node(models: dict, prompts: dict, cfg: "DebateConfig") -> Callable:
    def chair_summary_node(state: dict) -> dict:
        specialist_role = pick_specialist_for_round(state["rng_seed"], state["round"])
        system = prompts["chair_summary"]
        topic_ctx = state.get("topic_context") or "None provided."

        # Build digest of previous chair summaries for cross-round memory
        past_summaries = state.get("chair_summaries", [])
        if past_summaries:
            digests = []
            for i, s in enumerate(past_summaries, 1):
                digests.append(f"  Round {i}: {s[:cfg.chair_summary_digest_chars].replace(chr(10), ' ')}...")
            past_summary_block = "YOUR PREVIOUS ROUND SUMMARIES:\n" + "\n".join(digests)
        else:
            past_summary_block = ""

        # Build response block (may be empty in edge cases)
        sup_response = state.get('supporters_response', '')
        opp_response = state.get('opponents_response', '')
        response_block = ""
        if sup_response or opp_response:
            response_block = f"""
SUPPORTERS' RESPONSE TO INTERVENTION:
{sup_response[:400]}

OPPONENTS' RESPONSE TO INTERVENTION:
{opp_response[:400]}
"""

        specialist_choices = "devils_advocate, risk_officer, implementation_officer, evidence_auditor, red_team, second_order_analyst, wild_card"
        user = f"""DEBATE TOPIC: {state['topic']}
TOPIC CONTEXT: {topic_ctx}
ROUND {state['round']} of {state['max_rounds']}

SUPPORTERS said:
{state['supporters_speech'][:cfg.chair_summary_sup_chars]}

OPPONENTS said:
{state['opponents_speech'][:cfg.chair_summary_opp_chars]}

{specialist_role} said:
{state['third_party_speech'][:cfg.chair_summary_specialist_chars]}
{response_block}
{past_summary_block}

PREVIOUS CLAIM REGISTRY:
{state.get('claim_registry') or 'No claims tracked yet — this is the first round.'}

Write your round summary. Identify unresolved disputes. Issue a specific DIRECTIVE FOR NEXT ROUND. Then output an updated CLAIM REGISTRY. Recommend the most suitable specialist for the next round using [SPECIALIST: role] (choose from: {specialist_choices}). End with [DECISION: CONTINUE] or [DECISION: CONCLUDE] on its own line.
"""
        chair_model = state["role_map"]["chair"]
        speech = call_model(models, chair_model, system, user, cfg)
        should_continue = parse_chair_decision(speech)

        decision_str = "→ CONTINUE" if should_continue else "→ CONCLUDE"
        print(f"\n  [Chair Summary - {chair_model}] {decision_str}\n{speech}\n")
        _append_raw(state, "chair_summary", chair_model, speech)

        # Extract structured data from chair's output
        claim_registry = _extract_claim_registry(speech, state.get("claim_registry", ""))
        next_specialist = _extract_specialist_recommendation(speech)

        record = _make_record(state["round"], "chair", chair_model, speech)
        return {
            "chair_summary": speech,
            "chair_directive": speech,  # Update directive for next round's speakers
            "chair_summaries": [speech],
            "claim_registry": claim_registry,
            "next_specialist": next_specialist,
            "should_continue": should_continue,
            "history": [record],
        }
    return chair_summary_node


def make_write_output_node() -> Callable:
    def write_output_node(state: dict) -> dict:
        # Actual writing is handled in debate.py after graph.invoke returns.
        # This node is a no-op passthrough so the graph has a clean termination node.
        print(f"\n[INFO] Debate complete after {state['round']} round(s).")
        return {}
    return write_output_node
