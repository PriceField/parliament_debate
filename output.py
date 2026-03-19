"""Markdown output formatter for debate records."""

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config import DebateConfig
    from graph import DebateState

ROLE_EN_NAMES = {
    "主席": "Chair",
    "支持派": "Supporters",
    "反對派": "Opponents",
    "魔鬼辯護人": "Devil's Advocate",
    "風險官": "Risk Officer",
    "執行官": "Implementation Officer",
    "證據審計官": "Evidence Auditor",
    "紅隊": "Red Team",
    "二階效應分析師": "Second-Order Analyst",
    "奇兵": "Wild Card",
    "支持派_回應": "Supporters' Response",
    "反對派_回應": "Opponents' Response",
}


def generate_filename(state: dict, cfg: "DebateConfig") -> str:
    """Generate output path: outputs/<short_title>_<YYYYMMDD>/debate_<HHMMSS>.md"""
    short_title = state.get("short_title") or ""
    if not short_title:
        # Fallback: truncate topic
        short_title = re.sub(r"[^\w\u4e00-\u9fff]", "_", state.get("topic", "debate"))[:15]

    # Clean for filesystem safety
    safe_title = re.sub(r'[<>:"/\\|?*\s]', '_', short_title).strip('_')
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")

    folder = os.path.join(cfg.output_dir, f"{safe_title}_{date_str}")
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, f"debate_{time_str}.md")


def _role_table(role_map: dict, cfg: "DebateConfig") -> str:
    header = "| Role | 角色 | Model |\n|------|------|-------|"
    rows = []
    for role_zh, model_key in role_map.items():
        role_en = ROLE_EN_NAMES.get(role_zh, role_zh)
        model_display = cfg.model_display_names.get(model_key, model_key)
        rows.append(f"| {role_en} | {role_zh} | {model_display} |")
    return header + "\n" + "\n".join(rows)


def _format_speech(record: dict, cfg: "DebateConfig") -> str:
    role_zh = record["role_zh"]
    role_en = ROLE_EN_NAMES.get(role_zh, role_zh)
    model_key = record["model_name"]
    model_display = cfg.model_display_names.get(model_key, model_key)
    return f"### {role_en} ({role_zh}) [{model_display}]\n\n{record['content']}\n"


def assemble_markdown(state: dict, seed: Optional[int], cfg: "DebateConfig") -> str:
    lines = []

    # Header
    lines.append("# 議會辯論記錄\n## Parliamentary Debate Record\n")
    if state.get("short_title"):
        lines.append(f"**簡稱 (Short Title):** {state['short_title']}")
    lines.append(f"**辯題 (Topic):** {state['topic']}")
    lines.append(f"**日期 (Date):** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**完成輪次 (Rounds completed):** {state['round']}")
    if state.get("topic_context"):
        lines.append(f"**背景 (Context):** {state['topic_context']}")
    lines.append("\n---\n")

    # Role assignment table
    lines.append("## 角色分配 (Role Assignment)\n")
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
                lines.append("## 辯論開場 (Opening)\n")
                current_round = 0
        else:
            if r != current_round:
                current_round = r
                lines.append(f"## 第 {r} 輪 (Round {r})\n")

        lines.append(_format_speech(record, cfg))
        lines.append("---\n")

    # Analytics
    total_words = sum(len(r["content"].split()) for r in history)
    _NON_SPECIALIST_ROLES = {"主席", "支持派", "反對派", "支持派_回應", "反對派_回應"}
    specialist_records = [
        r for r in history
        if r["role_zh"] not in _NON_SPECIALIST_ROLES
    ]
    all_models = sorted(set(r["model_name"] for r in history))

    lines.append("## 辯論分析 (Debate Analytics)\n")
    lines.append(f"- **Total speeches:** {len(history)}")
    lines.append(f"- **Total words (estimated):** {total_words}")
    lines.append(f"- **Rounds completed:** {state['round']}")
    lines.append(f"- **Models participated:** {', '.join(cfg.model_display_names.get(m, m) for m in all_models)}")

    # Debate conclusion method
    if not state.get("should_continue"):
        lines.append("- **辯論結束方式 (Conclusion):** 主席主動結束 (Chair concluded)")
    else:
        lines.append("- **辯論結束方式 (Conclusion):** 達到回合上限 (Round limit reached)")

    # Specialist appearance table
    if specialist_records:
        lines.append("\n### 專家出場表 (Specialist Appearances)\n")
        lines.append("| Round | Specialist | 角色 | Model |")
        lines.append("|-------|-----------|------|-------|")
        for r in specialist_records:
            role_en = ROLE_EN_NAMES.get(r["role_zh"], r["role_zh"])
            model_display = cfg.model_display_names.get(r["model_name"], r["model_name"])
            lines.append(f"| {r['round']} | {role_en} | {r['role_zh']} | {model_display} |")

    # Claim Registry (final state)
    claim_registry = state.get("claim_registry", "")
    if claim_registry:
        lines.append("\n### 論點追蹤表 (Final Claim Registry)\n")
        lines.append(claim_registry)

    # Unresolved questions from last chair summary
    chair_summaries = state.get("chair_summaries", [])
    if chair_summaries:
        last_summary = chair_summaries[-1]
        lines.append("\n### 最後主席評述 (Final Chair Assessment)\n")
        # Extract just the summary part (before CLAIM REGISTRY section)
        summary_part = last_summary.split("CLAIM REGISTRY:")[0].strip()
        # Remove the decision tag
        summary_part = re.sub(r'\[DECISION:\s*(CONTINUE|CONCLUDE)\]', '', summary_part).strip()
        lines.append(summary_part)

    lines.append(
        f"\n---\n*Generated by Parliamentary Debate System | {datetime.now().isoformat()}*"
    )

    return "\n".join(lines)
