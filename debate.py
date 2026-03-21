"""Parliament Debate System — CLI entry point."""

import argparse
import hashlib
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import DebateConfig, load_config  # noqa: E402 — must follow load_dotenv()
from models import init_models
from assignment import parse_role_map_override, build_final_role_map, pick_specialist_for_round
from prompts import build_prompts
from graph import build_debate_graph
from output import assemble_markdown, generate_filename


def make_thread_id(topic: str, seed: int) -> str:
    h = hashlib.md5(f"{topic}_{seed}".encode()).hexdigest()[:8]
    return f"debate_{h}"


def list_sessions(cfg: DebateConfig) -> None:
    """Print all existing debate sessions from the checkpoint DB."""
    try:
        import sqlite3
        conn = sqlite3.connect(cfg.checkpoint_db)
        cur = conn.cursor()
        # LangGraph stores threads in a 'checkpoints' table
        cur.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
        )
        rows = cur.fetchall()
        conn.close()
        if rows:
            print("Existing debate sessions:")
            for (thread_id,) in rows:
                print(f"  {thread_id}")
            print(f"\nResume with: python debate.py --resume <session_id>")
        else:
            print("No saved sessions found.")
    except Exception as e:
        print(f"[ERROR] Could not read sessions: {e}")


def _should_ask_continue(total_rounds: int, original_rounds: int) -> bool:
    """Determine if we should pause and ask the user to continue.

    - Once total rounds > 9: ask every round.
    - Otherwise: ask every ``original_rounds`` rounds.
    """
    if total_rounds > 9:
        return True
    return total_rounds % original_rounds == 0


def _interactive_continuation(graph, config: dict, final_state: dict,
                              original_rounds: int, session_id: str) -> dict:
    """Prompt the user to continue the debate after each scheduled pause.

    Returns the final state when the user declines or the chair concludes.
    """
    while True:
        total_rounds = final_state["round"]

        if not _should_ask_continue(total_rounds, original_rounds):
            # Not a pause point yet — extend silently
            interval = original_rounds - (total_rounds % original_rounds)
        else:
            # Ask the user
            print(f"\n{'─'*60}")
            print(f"  Round {total_rounds} complete.")
            print(f"{'─'*60}")
            try:
                answer = input("Continue debate? [y/N]: ")
            except (EOFError, KeyboardInterrupt):
                print("\n[INFO] Ending debate.")
                break
            if answer.strip().lower() != "y":
                break
            interval = 1 if total_rounds >= 9 else original_rounds

        new_max = total_rounds + interval
        # Resume from chair_summary so the conditional edge re-evaluates
        # with the updated max_rounds and routes to continue_debate.
        graph.update_state(config, {"max_rounds": new_max, "should_continue": True},
                           as_node="chair_summary")

        try:
            final_state = graph.invoke(None, config=config)
        except KeyboardInterrupt:
            print(f"\n[INFO] Debate interrupted. Resume with: python debate.py --resume {session_id}")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] Debate interrupted: {e}")
            print(f"[INFO] Resume with: python debate.py --resume {session_id}")
            sys.exit(1)

    return final_state


def run_debate(args: argparse.Namespace, cfg: DebateConfig) -> None:
    interactive = cfg.interactive and not args.no_interactive

    # Determine seed
    seed = args.seed if args.seed is not None else random.randint(0, 99999)
    print(f"[INFO] Role assignment seed: {seed}")

    # Initialize models first so ASSIGNABLE_MODELS is populated before role assignment
    print("\n[INFO] Initializing models...")
    models = init_models(cfg)
    print("[INFO] All models ready.")

    # Build role map (uses ASSIGNABLE_MODELS populated above)
    override = parse_role_map_override(args.role_map)
    role_map = build_final_role_map(override, seed=seed)

    print("[INFO] Role assignments:")
    for role, model in role_map.items():
        print(f"  {role:12s} → {model}")

    # Print specialist preview for round 1
    preview = [pick_specialist_for_round(seed, r) for r in range(1, args.rounds + 1)]
    print(f"[INFO] Specialist preview (may differ on run): {preview}")

    prompts = build_prompts()
    graph = build_debate_graph(models, prompts, cfg)

    thread_id = make_thread_id(args.topic, seed)
    config = {"configurable": {"thread_id": thread_id}}
    print(f"[INFO] Session ID: {thread_id}")
    print(f"[INFO] To resume if interrupted: python debate.py --resume {thread_id}")
    mode_label = "interactive" if interactive else "non-interactive"
    print(f"\n{'='*60}")
    print(f"  TOPIC: {args.topic}")
    print(f"  ROUNDS: {args.rounds}  ({mode_label})")
    print(f"{'='*60}")

    initial_state = {
        "topic": args.topic,
        "topic_context": args.context or "",
        "round": 0,
        "max_rounds": args.rounds,
        "role_map": role_map,
        "rng_seed": seed,
        "history": [],
        "chair_summaries": [],
        "claim_registry": "",
        "next_specialist": "",
        "chair_directive": "",
        "supporters_speech": "",
        "opponents_speech": "",
        "third_party_speech": "",
        "supporters_response": "",
        "opponents_response": "",
        "chair_summary": "",
        "short_title": "",
        "should_continue": True,
        "raw_output_path": "",
    }

    try:
        final_state = graph.invoke(initial_state, config=config)
    except KeyboardInterrupt:
        raw_path = initial_state.get("raw_output_path") or "check outputs/ folder"
        print(f"\n[INFO] Debate interrupted by user.")
        print(f"[INFO] Raw output so far: {raw_path}")
        print(f"[INFO] Resume with: python debate.py --resume {thread_id}")
        sys.exit(0)
    except Exception as e:
        raw_path = initial_state.get("raw_output_path") or "check outputs/ folder"
        print(f"\n[ERROR] Debate interrupted: {e}")
        print(f"[INFO] Raw output so far: {raw_path}")
        print(f"[INFO] Session saved. Resume with: python debate.py --resume {thread_id}")
        sys.exit(1)

    # Interactive continuation: ask user whether to extend
    if interactive:
        final_state = _interactive_continuation(
            graph, config, final_state, args.rounds, thread_id,
        )

    # Write formatted output (raw file already written incrementally by nodes)
    raw_path = final_state.get("raw_output_path", "")
    try:
        md_content = assemble_markdown(final_state, seed, cfg)
        output_file = args.output or generate_filename(final_state, cfg)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(md_content, encoding="utf-8")
        print(f"\n[INFO] Formatted output: {output_file}")
    except Exception as e:
        print(f"\n[ERROR] Failed to write formatted output: {e}")
    if raw_path:
        print(f"[INFO] Raw output: {raw_path}")


def resume_debate(session_id: str, output_file: str | None,
                   cfg: DebateConfig, *, no_interactive: bool = False) -> None:
    """Resume a previously interrupted debate."""
    interactive = cfg.interactive and not no_interactive
    print(f"[INFO] Resuming session: {session_id}")

    models = init_models(cfg)
    prompts = build_prompts()
    graph = build_debate_graph(models, prompts, cfg)

    config = {"configurable": {"thread_id": session_id}}

    try:
        # Pass None as state to resume from checkpoint
        final_state = graph.invoke(None, config=config)
    except KeyboardInterrupt:
        print(f"\n[INFO] Debate interrupted again. Resume with: python debate.py --resume {session_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Resume failed: {e}")
        print(f"[INFO] Try again with: python debate.py --resume {session_id}")
        sys.exit(1)

    # Interactive continuation after resumed rounds complete
    if interactive:
        original_rounds = cfg.default_rounds
        final_state = _interactive_continuation(
            graph, config, final_state, original_rounds, session_id,
        )

    # Extract seed from state if available (for header)
    seed = final_state.get("rng_seed")

    raw_path = final_state.get("raw_output_path", "")
    try:
        md_content = assemble_markdown(final_state, seed, cfg)
        out = output_file or generate_filename(final_state, cfg)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(md_content, encoding="utf-8")
        print(f"\n[INFO] Formatted output: {out}")
    except Exception as e:
        print(f"\n[ERROR] Failed to write formatted output: {e}")
    if raw_path:
        print(f"[INFO] Raw output: {raw_path}")


def main() -> None:
    cfg = load_config()

    parser = argparse.ArgumentParser(
        description="Parliamentary Debate System — multi-model LangGraph debate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python debate.py --topic "Should AI be regulated by governments?" --rounds 4
  python debate.py --topic "..." --role-map '{"supporters":"gpt4o","opponents":"gemini"}' --rounds 3
  python debate.py --topic "..." --seed 42137
  python debate.py --resume debate_3a7f92c1
  python debate.py --list-sessions
        """,
    )

    parser.add_argument("--topic", type=str, help="Debate topic (required unless --resume or --list-sessions)")
    parser.add_argument("--rounds", type=int, default=cfg.default_rounds, help="Maximum rounds (default: 3)")
    parser.add_argument(
        "--role-map",
        type=str,
        default=None,
        metavar="JSON",
        help='Initial role→model assignment override, e.g. \'{"supporters":"gpt4o","opponents":"gemini"}\'',
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for role assignment")
    parser.add_argument("--context", type=str, default="", help="Additional background context for the topic")
    parser.add_argument("--output", type=str, default=None, help="Output filename (default: auto-generated)")
    parser.add_argument("--resume", type=str, default=None, metavar="SESSION_ID", help="Resume an interrupted debate session")
    parser.add_argument("--no-interactive", action="store_true", help="Disable interactive continuation (end after planned rounds)")
    parser.add_argument("--list-sessions", action="store_true", help="List all saved debate sessions")

    args = parser.parse_args()

    if args.list_sessions:
        list_sessions(cfg)
        return

    if args.resume:
        resume_debate(args.resume, args.output, cfg, no_interactive=args.no_interactive)
        return

    if not args.topic:
        parser.error("--topic is required unless using --resume or --list-sessions")

    run_debate(args, cfg)


if __name__ == "__main__":
    main()
