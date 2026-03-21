"""Markdown output formatter for debate records."""

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config import DebateConfig
    from graph import DebateState

def _sanitize_filename(s: str) -> str:
    """Replace filesystem-unsafe characters and whitespace with underscores."""
    return re.sub(r'[<>:"/\\|?*\s]', '_', s).strip('_')


def _make_output_folder(short_title: str, cfg: "DebateConfig") -> tuple[str, str]:
    """Create the date-stamped output folder and return (folder_path, time_str)."""
    safe_title = _sanitize_filename(short_title) or "debate"
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")
    folder = os.path.join(cfg.output_dir, f"{safe_title}_{date_str}")
    os.makedirs(folder, exist_ok=True)
    return folder, time_str


ROLE_DISPLAY_NAMES = {
    "chair": "Chair",
    "supporters": "Supporters",
    "opponents": "Opponents",
    "devils_advocate": "Devil's Advocate",
    "risk_officer": "Risk Officer",
    "implementation_officer": "Implementation Officer",
    "evidence_auditor": "Evidence Auditor",
    "red_team": "Red Team",
    "second_order_analyst": "Second-Order Analyst",
    "wild_card": "Wild Card",
    "supporters_response": "Supporters' Response",
    "opponents_response": "Opponents' Response",
}


def generate_filename(state: dict, cfg: "DebateConfig") -> str:
    """Generate output path: outputs/<short_title>_<YYYYMMDD>/debate_<HHMMSS>.md"""
    short_title = state.get("short_title") or ""
    if not short_title:
        short_title = re.sub(r"[^\w]", "_", state.get("topic", "debate"))[:15]
    folder, time_str = _make_output_folder(short_title, cfg)
    return os.path.join(folder, f"debate_{time_str}.md")


def generate_raw_filepath(short_title: str, cfg: "DebateConfig") -> str:
    """Generate raw output path: outputs/<short_title>_<YYYYMMDD>/debate_raw_<HHMMSS>.txt"""
    folder, time_str = _make_output_folder(short_title, cfg)
    return os.path.join(folder, f"debate_raw_{time_str}.txt")


def _role_table(role_map: dict, cfg: "DebateConfig") -> str:
    header = "| Role | Model |\n|------|-------|"
    rows = []
    for role_key, model_key in role_map.items():
        role_display = ROLE_DISPLAY_NAMES.get(role_key, role_key)
        model_display = cfg.model_aliases.get(model_key, model_key)
        rows.append(f"| {role_display} | {model_display} |")
    return header + "\n" + "\n".join(rows)


def _format_speech(record: dict, cfg: "DebateConfig") -> str:
    role_key = record["role_zh"]
    role_display = ROLE_DISPLAY_NAMES.get(role_key, role_key)
    model_key = record["model_name"]
    model_display = cfg.model_aliases.get(model_key, model_key)
    return f"### {role_display} [{model_display}]\n\n{record['content']}\n"


def assemble_markdown(state: dict, seed: Optional[int], cfg: "DebateConfig") -> str:
    lines = []

    # Header
    lines.append("# Parliamentary Debate Record\n")
    if state.get("short_title"):
        lines.append(f"**Short Title:** {state['short_title']}")
    lines.append(f"**Topic:** {state['topic']}")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Rounds completed:** {state['round']}")
    if state.get("topic_context"):
        lines.append(f"**Context:** {state['topic_context']}")
    lines.append("\n---\n")

    # Role assignment table
    lines.append("## Role Assignment\n")
    lines.append(_role_table(state["role_map"], cfg))
    seed_display = seed if seed is not None else "random"
    lines.append(f"\n> Role assignment seed: `{seed_display}` — use `--seed {seed_display}` to reproduce\n")
    lines.append("---\n")

    # Speeches grouped by round
    history = state.get("history", [])
    current_round = -1

    for record in history:
        r = record["round"]
        if r == 0:
            if current_round != 0:
                lines.append("## Opening\n")
                current_round = 0
        else:
            if r != current_round:
                current_round = r
                lines.append(f"## Round {r}\n")

        lines.append(_format_speech(record, cfg))
        lines.append("---\n")

    # Analytics
    total_words = sum(len(r["content"].split()) for r in history)
    _NON_SPECIALIST_ROLES = {"chair", "supporters", "opponents", "supporters_response", "opponents_response"}
    specialist_records = [
        r for r in history
        if r["role_zh"] not in _NON_SPECIALIST_ROLES
    ]
    all_models = sorted(set(r["model_name"] for r in history))

    lines.append("## Debate Analytics\n")
    lines.append(f"- **Total speeches:** {len(history)}")
    lines.append(f"- **Total words (estimated):** {total_words}")
    lines.append(f"- **Rounds completed:** {state['round']}")
    lines.append(f"- **Models participated:** {', '.join(cfg.model_aliases.get(m, m) for m in all_models)}")

    # Debate conclusion method
    if not state.get("should_continue"):
        lines.append("- **Conclusion:** Chair concluded")
    else:
        lines.append("- **Conclusion:** Round limit reached")

    # Specialist appearance table
    if specialist_records:
        lines.append("\n### Specialist Appearances\n")
        lines.append("| Round | Specialist | Model |")
        lines.append("|-------|-----------|-------|")
        for r in specialist_records:
            role_display = ROLE_DISPLAY_NAMES.get(r["role_zh"], r["role_zh"])
            model_display = cfg.model_aliases.get(r["model_name"], r["model_name"])
            lines.append(f"| {r['round']} | {role_display} | {model_display} |")

    # Claim Registry (final state)
    claim_registry = state.get("claim_registry", "")
    if claim_registry:
        lines.append("\n### Final Claim Registry\n")
        lines.append(claim_registry)

    # Unresolved questions from last chair summary
    chair_summaries = state.get("chair_summaries", [])
    if chair_summaries:
        last_summary = chair_summaries[-1]
        lines.append("\n### Final Chair Assessment\n")
        # Extract just the summary part (before CLAIM REGISTRY section)
        summary_part = last_summary.split("CLAIM REGISTRY:")[0].strip()
        # Remove the decision tag
        summary_part = re.sub(r'\[DECISION:\s*(CONTINUE|CONCLUDE)\]', '', summary_part).strip()
        lines.append(summary_part)

    lines.append(
        f"\n---\n*Generated by Parliamentary Debate System | {datetime.now().isoformat()}*"
    )

    return "\n".join(lines)
