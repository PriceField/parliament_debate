Parliament Debate System — multi-model AI debate simulator. LangGraph StateGraph drives Claude/GPT/Gemini/Grok through 10 roles in multi-round parliamentary debates. SQLite checkpointing. Dual output: incremental raw .txt + final formatted .md.

Modules:
debate.py — CLI entry point, argparse, run/resume/list-sessions, interactive continuation
config.py — DebateConfig dataclass, all env vars, single source of truth
models.py — model init (ChatAnthropic/OpenAI/Google/xAI), call_model with retry
assignment.py — role-to-model assignment (seeded random), pick_specialist_for_round
prompts.py — 13 prompt strings via build_prompts()
nodes.py — LangGraph node factories, _build_context truncation, chair tag parsing
graph.py — DebateState TypedDict, SpeechRecord, StateGraph wiring, SQLite checkpointer
output.py — assemble_markdown(), raw filepath generation, ROLE_DISPLAY_NAMES

Docs:
docs/architecture.md — module deps, startup sequence, session persistence, output paths
docs/state-and-flow.md — DebateState fields, node sequence, routing, context truncation, chair tags
docs/config-reference.md — all env vars with defaults, preset config comparison
docs/roles-and-prompts.md — 10 roles, prompt rules, specialist rotation, assignment logic

Invariants:
Chair is always Claude — assign_roles() hardcodes {"chair": "claude"}, init_models requires ANTHROPIC_API_KEY
history uses Annotated[list, operator.add] — each node returns only new records, never overwrite the whole list
chair_summary doubles as next round chair_directive — chair_summary_node returns {"chair_directive": speech}
Thread ID = debate_<md5(topic + "_" + seed)[:8]> — same topic+seed always produces same ID
write_output_node is a no-op — real markdown write happens in debate.py _write_formatted_output after graph completes
