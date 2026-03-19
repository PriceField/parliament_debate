"""Quick sanity-check: call each configured model with a one-liner prompt."""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from config import load_config
from models import init_models, call_model, _MODEL_KEY_MAP

PING_SYSTEM = "You are a helpful assistant."
PING_USER   = "Reply with exactly: OK"


def test_all_models() -> None:
    cfg = load_config()

    # Detect which models have keys set
    candidates = {
        key: env_key
        for key, env_key in _MODEL_KEY_MAP.items()
        if os.getenv(env_key)
    }

    if not candidates:
        print("[ERROR] No API keys found — check your .env file.")
        sys.exit(1)

    print(f"Keys detected: {list(candidates.keys())}\n")

    try:
        models = init_models(cfg)
    except EnvironmentError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    passed, failed = [], []

    for key in models:
        model_name = cfg.model_aliases.get(key, key)
        print(f"Testing {key} ({model_name}) ... ", end="", flush=True)
        try:
            reply = call_model(models, key, PING_SYSTEM, PING_USER, cfg)
            snippet = reply.strip().replace("\n", " ")[:60]
            print(f"OK  ->  \"{snippet}\"")
            passed.append(key)
        except Exception as e:
            print(f"FAIL  ->  {e}")
            failed.append(key)

    print(f"\n{'='*40}")
    print(f"Passed: {passed}")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)
    else:
        print("All models reachable.")


if __name__ == "__main__":
    test_all_models()
