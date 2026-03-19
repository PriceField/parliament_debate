"""Centralized configuration — single source of truth for all env-driven settings."""

import os
from dataclasses import dataclass


@dataclass
class DebateConfig:
    """All environment-driven configuration in one place.

    Created once via ``load_config()`` after ``load_dotenv()`` and threaded
    through the application as a plain parameter (lightweight DI).
    """

    # ── Model names ───────────────────────────────────────────────────────
    claude_model: str
    openai_model: str
    google_model: str
    grok_model: str

    # ── API Endpoints（None = 使用官方預設）─────────────────────────────
    anthropic_base_url: str | None
    openai_base_url: str | None
    google_base_url: str | None
    xai_base_url: str | None

    # ── Model behaviour ───────────────────────────────────────────────────
    max_output_tokens: int
    temperature: float
    call_retries: int
    backoff_base: int

    # ── Debate settings ───────────────────────────────────────────────────
    checkpoint_db: str
    default_rounds: int

    # ── Context truncation (used by nodes) ────────────────────────────────
    max_history_chars: int
    opening_digest_chars: int
    summary_digest_chars: int
    full_detail_rounds: int
    chair_summary_sup_chars: int
    chair_summary_opp_chars: int
    chair_summary_specialist_chars: int
    chair_summary_digest_chars: int

    # ── Output ────────────────────────────────────────────────────────────
    filename_topic_chars: int

    # ── Derived helpers ───────────────────────────────────────────────────

    @property
    def model_aliases(self) -> dict[str, str]:
        return {
            "claude": self.claude_model,
            "gpt4o": self.openai_model,
            "gemini": self.google_model,
            "grok": self.grok_model,
        }

    @property
    def model_display_names(self) -> dict[str, str]:
        return self.model_aliases


def load_config() -> DebateConfig:
    """Read all env vars and return a frozen snapshot.

    Env var names and defaults are identical to the previous scattered reads.
    """
    return DebateConfig(
        # Model names
        claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        google_model=os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview"),
        grok_model=os.getenv("GROK_MODEL", "grok-3-mini"),
        # API Endpoints
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        google_base_url=os.getenv("GOOGLE_BASE_URL") or None,
        xai_base_url=os.getenv("XAI_BASE_URL") or None,
        # Model behaviour
        max_output_tokens=int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "1024")),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7")),
        call_retries=int(os.getenv("MODEL_CALL_RETRIES", "3")),
        backoff_base=int(os.getenv("MODEL_BACKOFF_BASE", "2")),
        # Debate
        checkpoint_db=os.getenv("DEBATE_CHECKPOINT_DB", "debate_checkpoints.db"),
        default_rounds=int(os.getenv("DEBATE_DEFAULT_ROUNDS", "3")),
        # Context truncation
        max_history_chars=int(os.getenv("DEBATE_MAX_HISTORY_CHARS", "12000")),
        opening_digest_chars=int(os.getenv("DEBATE_OPENING_DIGEST_CHARS", "200")),
        summary_digest_chars=int(os.getenv("DEBATE_SUMMARY_DIGEST_CHARS", "150")),
        full_detail_rounds=int(os.getenv("DEBATE_FULL_DETAIL_ROUNDS", "2")),
        chair_summary_sup_chars=int(os.getenv("CHAIR_SUMMARY_SUP_CHARS", "800")),
        chair_summary_opp_chars=int(os.getenv("CHAIR_SUMMARY_OPP_CHARS", "800")),
        chair_summary_specialist_chars=int(os.getenv("CHAIR_SUMMARY_SPECIALIST_CHARS", "600")),
        chair_summary_digest_chars=int(os.getenv("CHAIR_SUMMARY_DIGEST_CHARS", "500")),
        # Output
        filename_topic_chars=int(os.getenv("DEBATE_FILENAME_TOPIC_CHARS", "30")),
    )
