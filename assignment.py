"""Role-to-model assignment logic."""

import json
import random
from typing import Optional

import models as _models_module

DEBATE_ROLES = [
    "主席",
    "支持派",
    "反對派",
    "魔鬼辯護人",
    "風險官",
    "執行官",
    "證據審計官",
    "紅隊",
    "二階效應分析師",
    "奇兵",
]

SPECIALIST_ROLES = [
    "魔鬼辯護人",
    "風險官",
    "執行官",
    "證據審計官",
    "紅隊",
    "二階效應分析師",
    "奇兵",
]

# Roles that can be assigned (Chair is always Claude)
ASSIGNABLE_ROLES = [r for r in DEBATE_ROLES if r != "主席"]


def assign_roles(seed: Optional[int] = None) -> dict[str, str]:
    """
    Assign models to roles with two guarantees:
    1. Chair is always Claude.
    2. Every available model appears at least once.

    Returns: {role_zh: model_key}
    """
    rng = random.Random(seed)
    role_map = {"主席": "claude"}

    roles = ASSIGNABLE_ROLES.copy()
    # Read at call time so init_models() has already populated the list
    available = _models_module.ASSIGNABLE_MODELS
    if not available:
        raise RuntimeError("ASSIGNABLE_MODELS is empty — call init_models() first.")
    models = [m for m in available if m != "claude"]  # claude is always chair
    if not models:
        # Only claude available: assign it to all non-chair roles too
        models = ["claude"]

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

    valid_models = set(_models_module.ALL_MODELS)
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
    seed: Optional[int] = None,
) -> dict[str, str]:
    """Merge random assignment with user overrides. Override takes precedence."""
    random_assignment = assign_roles(seed=seed)
    final = {**random_assignment, **override}

    # Validate all specialist roles are covered
    used_models = set(v for k, v in final.items() if k != "主席")
    missing_models = set(_models_module.ASSIGNABLE_MODELS) - used_models
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
