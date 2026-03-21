"""Role-to-model assignment logic."""

import json
import random
from typing import Optional

from models import ALL_MODELS

DEBATE_ROLES = [
    "chair",
    "supporters",
    "opponents",
    "devils_advocate",
    "risk_officer",
    "implementation_officer",
    "evidence_auditor",
    "red_team",
    "second_order_analyst",
    "wild_card",
]

SPECIALIST_ROLES = [
    "devils_advocate",
    "risk_officer",
    "implementation_officer",
    "evidence_auditor",
    "red_team",
    "second_order_analyst",
    "wild_card",
]

# Roles that can be assigned (Chair is always Claude)
ASSIGNABLE_ROLES = [r for r in DEBATE_ROLES if r != "chair"]


def assign_roles(available_models: list[str], seed: Optional[int] = None) -> dict[str, str]:
    """
    Assign models to roles with two guarantees:
    1. Chair is always Claude.
    2. Every available model appears at least once.

    Returns: {role_key: model_key}
    """
    if not available_models:
        raise RuntimeError("available_models is empty — no models initialized.")
    rng = random.Random(seed)
    role_map = {"chair": "claude"}

    roles = ASSIGNABLE_ROLES.copy()
    models = list(available_models)

    # Phase 1: Guarantee every model gets at least one role
    guaranteed_models = models.copy()
    rng.shuffle(guaranteed_models)
    rng.shuffle(roles)

    for i, model in enumerate(guaranteed_models):
        role_map[roles[i]] = model

    # Phase 2: Randomly assign remaining roles
    remaining_roles = roles[len(guaranteed_models):]
    for role in remaining_roles:
        role_map[role] = rng.choice(models)

    return role_map


def parse_role_map_override(raw: Optional[str]) -> dict[str, str]:
    """Parse --role-map JSON string into a partial override dict."""
    if not raw:
        return {}
    try:
        override = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--role-map must be valid JSON: {e}")

    valid_models = set(ALL_MODELS)
    valid_roles = set(DEBATE_ROLES)

    cleaned = {}
    for role, model in override.items():
        if role not in valid_roles:
            print(f"[WARN] Unknown role '{role}'. Valid roles: {sorted(valid_roles)}")
            continue
        if model not in valid_models:
            raise ValueError(
                f"Unknown model '{model}' for role '{role}'. Valid: {sorted(valid_models)}"
            )
        cleaned[role] = model

    return cleaned


def build_final_role_map(
    override: dict[str, str],
    available_models: list[str],
    seed: Optional[int] = None,
) -> dict[str, str]:
    """Merge random assignment with user overrides. Override takes precedence."""
    random_assignment = assign_roles(available_models, seed=seed)
    final = {**random_assignment, **override}

    # Validate all specialist roles are covered
    used_models = set(v for k, v in final.items() if k != "chair")
    missing_models = set(available_models) - used_models
    if missing_models:
        print(
            f"[WARN] After override, models {missing_models} have no assigned role. "
            "Consider adjusting --role-map."
        )

    # Ensure all specialist roles exist in role_map (startup-time validation)
    missing_specialist_keys = [r for r in SPECIALIST_ROLES if r not in final]
    if missing_specialist_keys:
        raise ValueError(
            f"BUG: Specialist roles missing from role_map: {missing_specialist_keys}. "
            "This should not happen. Check assign_roles()."
        )

    return final


def pick_specialist_for_round(seed: int, round_num: int) -> str:
    """Pick a random specialist role for the given round (deterministic with seed)."""
    rng = random.Random(seed + round_num)
    return rng.choice(SPECIALIST_ROLES)
