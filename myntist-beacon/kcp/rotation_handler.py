"""
Key Continuity Protocol — rotation handler.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

from .key_state import (
    KeyState,
    create_genesis,
    get_latest_key_state,
    load_key_states,
    save_key_states,
)


def rotate_key(
    new_public_key: str,
    threshold_m: Optional[int] = None,
    threshold_n: Optional[int] = None,
) -> KeyState:
    """
    Rotate to a new key state.

    - Loads current state
    - Increments version
    - Sets parent_key_state_hash to the hash of the prior state
    - Appends new state and persists

    Args:
        new_public_key:  The new public key string
        threshold_m:     New M threshold (defaults to prior value)
        threshold_n:     New N threshold (defaults to prior value)

    Returns:
        The newly created KeyState
    """
    current = get_latest_key_state()

    if current is None:
        return create_genesis(new_public_key, threshold_m or 2, threshold_n or 3)

    parent_hash = current.compute_hash()
    new_state = KeyState(
        version=current.version + 1,
        public_key=new_public_key,
        threshold_m=threshold_m if threshold_m is not None else current.threshold_m,
        threshold_n=threshold_n if threshold_n is not None else current.threshold_n,
        parent_key_state_hash=parent_hash,
        created_at=time.time(),
        signature_chain=list(current.signature_chain) + [parent_hash],
    )

    states = load_key_states()
    states.append(new_state)
    save_key_states(states)
    return new_state


def initialize_if_needed(default_public_key: str = "genesis-key-placeholder") -> KeyState:
    """Ensure at least a genesis state exists."""
    existing = get_latest_key_state()
    if existing is not None:
        return existing
    return create_genesis(default_public_key)


def check_key_age(
    max_age_days: Optional[int] = None,
    created_env: str = "ED25519_KEY_CREATED",
) -> dict:
    """
    Check whether the Ed25519 signing key has exceeded its maximum permitted age.

    Reads the key creation date from the environment variable named by *created_env*
    (default: ``ED25519_KEY_CREATED``, expected ISO format: ``YYYY-MM-DD``).
    Returns a result dict with ``age_days``, ``max_age_days``, ``rotation_required``,
    and ``warning`` (a human-readable message when rotation is needed).

    This function is called by:
    - The APScheduler job in ``role_decay.py`` every 24 hours.
    - Operators running diagnostics manually.

    Example::

        from kcp.rotation_handler import check_key_age
        result = check_key_age()
        if result["rotation_required"]:
            print(result["warning"])

    Args:
        max_age_days:  Override the default maximum key age in days.
                       Falls back to the ``KEY_MAX_AGE_DAYS`` env var (default 90).
        created_env:   Name of the environment variable holding the creation date.

    Returns:
        dict with keys: age_days, max_age_days, rotation_required, warning
    """
    _max_age = max_age_days or int(os.environ.get("KEY_MAX_AGE_DAYS", "330"))
    created_str = os.environ.get(created_env, "")

    if not created_str:
        msg = (
            f"{created_env} is not set — cannot verify key age. "
            "Set it in SSM or .env (format: YYYY-MM-DD)."
        )
        logger.warning("check_key_age: %s", msg)
        return {
            "age_days": None,
            "max_age_days": _max_age,
            "rotation_required": False,
            "warning": msg,
        }

    try:
        created = date.fromisoformat(created_str)
    except ValueError as exc:
        msg = f"Invalid {created_env}={created_str!r}: {exc}"
        logger.warning("check_key_age: %s", msg)
        return {
            "age_days": None,
            "max_age_days": _max_age,
            "rotation_required": False,
            "warning": msg,
        }

    age_days = (date.today() - created).days
    rotation_required = age_days > _max_age

    if rotation_required:
        warning = (
            f"Ed25519 signing key is {age_days} days old "
            f"(max {_max_age} days) — rotation required. "
            "See ROTATION_POLICY.md for the rotation runbook."
        )
        logger.warning("check_key_age: %s", warning)
    else:
        warning = ""
        logger.info(
            "check_key_age: key age=%d days (max=%d) — OK",
            age_days,
            _max_age,
        )

    return {
        "age_days": age_days,
        "max_age_days": _max_age,
        "rotation_required": rotation_required,
        "warning": warning,
    }
