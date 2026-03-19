"""Model initialization and unified call wrapper."""

import os
import time
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_xai import ChatXAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

if TYPE_CHECKING:
    from config import DebateConfig

# Full list of supported model keys (used for validation)
ALL_MODELS = ["claude", "gpt4o", "gemini", "grok"]

# Map from model key → (env key name, model name env var)
_MODEL_KEY_MAP = {
    "claude": "ANTHROPIC_API_KEY",
    "gpt4o": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "grok": "XAI_API_KEY",
}

ASSIGNABLE_MODELS: list[str] = []  # populated by init_models()


def _get_available_models(cfg: "DebateConfig") -> list[str]:
    """Return model keys that have both an API key and a model name configured."""
    aliases = cfg.model_aliases
    available = []
    for key, env_key in _MODEL_KEY_MAP.items():
        if os.getenv(env_key) and aliases.get(key):
            available.append(key)
    return available


def init_models(cfg: "DebateConfig") -> dict[str, BaseChatModel]:
    """Initialize model clients for all available (key + model) pairs.

    Updates the global ASSIGNABLE_MODELS list so assignment.py sees which
    models are actually usable.  Requires at least Claude (chair).
    """
    global ASSIGNABLE_MODELS
    available = _get_available_models(cfg)

    if "claude" not in available:
        raise EnvironmentError("ANTHROPIC_API_KEY is required (Claude is the chair).")

    ASSIGNABLE_MODELS = available

    skipped = [k for k in ALL_MODELS if k not in available]
    if skipped:
        print(f"[INFO] Models skipped (no key/model configured): {skipped}")

    aliases = cfg.model_aliases

    result: dict[str, BaseChatModel] = {}

    if "claude" in available:
        claude_kwargs: dict = {
            "model": aliases["claude"],
            "max_tokens": cfg.max_output_tokens,
            "temperature": cfg.temperature,
        }
        if cfg.anthropic_base_url:
            claude_kwargs["base_url"] = cfg.anthropic_base_url
        result["claude"] = ChatAnthropic(**claude_kwargs)

    if "gpt4o" in available:
        openai_kwargs: dict = {
            "model": aliases["gpt4o"],
            "max_tokens": cfg.max_output_tokens,
            "temperature": cfg.temperature,
        }
        if cfg.openai_base_url:
            openai_kwargs["base_url"] = cfg.openai_base_url
        result["gpt4o"] = ChatOpenAI(**openai_kwargs)

    if "gemini" in available:
        safety_settings = None
        try:
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
        except ImportError:
            pass
        gemini_kwargs: dict = {
            "model": aliases["gemini"],
            "max_output_tokens": cfg.max_output_tokens,
            "temperature": cfg.temperature,
        }
        if safety_settings:
            gemini_kwargs["safety_settings"] = safety_settings
        if cfg.google_base_url:
            gemini_kwargs["client_options"] = {"api_endpoint": cfg.google_base_url}
        result["gemini"] = ChatGoogleGenerativeAI(**gemini_kwargs)

    if "grok" in available:
        xai_kwargs: dict = {
            "model": aliases["grok"],
            "max_tokens": cfg.max_output_tokens,
            "temperature": cfg.temperature,
        }
        if cfg.xai_base_url:
            xai_kwargs["base_url"] = cfg.xai_base_url
        result["grok"] = ChatXAI(**xai_kwargs)

    return result


def call_model(
    models: dict[str, BaseChatModel],
    model_key: str,
    system_prompt: str,
    user_message: str,
    cfg: "DebateConfig",
) -> str:
    """Unified model call with exponential backoff retry."""
    model = models[model_key]
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    for attempt in range(cfg.call_retries):
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            if attempt == cfg.call_retries - 1:
                raise
            wait = cfg.backoff_base ** attempt
            print(f"[WARN] {model_key} call failed (attempt {attempt + 1}/{cfg.call_retries}): {e}")
            print(f"[WARN] Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Model {model_key} failed after {cfg.call_retries} attempts")
