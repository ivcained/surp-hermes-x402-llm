"""Persistent per-profile routing preferences for Surp chat requests.

The user can flip these mid-conversation with the ``surp_route_prefs`` tool;
they are merged into every ``surp_chat`` call as Surplus Intelligence routing
controls (``providers_blocked``, ``provider_order``, ``si_route``) and the
``X-SI-Mask-Secrets`` header.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_PREFS = {
    "trusted_only": False,
    "block_providers": [],
    "prefer_providers": [],
    "objective": None,  # "price" | "latency" | "balanced" | None (router default)
    "mask_secrets": False,
}

_VALID_OBJECTIVES = ("price", "latency", "balanced")


def _hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME")
    return Path(home) if home else Path.home() / ".hermes"


def _prefs_path() -> Path:
    return _hermes_home() / "cache" / "surp-hermes-x402-llm" / "route-prefs.json"


def load_prefs() -> dict:
    prefs = dict(DEFAULT_PREFS)
    try:
        raw = json.loads(_prefs_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            prefs.update({k: v for k, v in raw.items() if k in DEFAULT_PREFS})
    except (OSError, ValueError):
        pass
    return _sanitize(prefs)


def save_prefs(prefs: dict) -> dict:
    prefs = _sanitize(prefs)
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(prefs, handle, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return prefs


def _sanitize(prefs: dict) -> dict:
    clean = dict(DEFAULT_PREFS)
    clean["trusted_only"] = bool(prefs.get("trusted_only", False))
    clean["block_providers"] = _provider_list(prefs.get("block_providers"))
    clean["prefer_providers"] = _provider_list(prefs.get("prefer_providers"))
    objective = prefs.get("objective")
    if objective in _VALID_OBJECTIVES:
        clean["objective"] = objective
    elif objective in (None, "", "default", "none"):
        clean["objective"] = None
    else:
        raise ValueError(
            f"objective must be one of price, latency, balanced (got {objective!r})"
        )
    clean["mask_secrets"] = bool(prefs.get("mask_secrets", False))
    return clean


def _provider_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    seen = []
    for item in value:
        name = str(item or "").strip().lower()
        if name and name not in seen:
            seen.append(name)
    return seen


def routing_controls(prefs: dict, blocked_from_trust: list[str] | None = None) -> dict:
    """Translate preferences into Surplus Intelligence request-body routing controls."""
    controls = {}
    blocked = list(_provider_list(prefs.get("block_providers")))
    if blocked_from_trust:
        blocked += [p for p in blocked_from_trust if p not in blocked]
    if blocked:
        controls["providers_blocked"] = blocked
    prefer = _provider_list(prefs.get("prefer_providers"))
    if prefer:
        controls["provider_order"] = prefer
    objective = prefs.get("objective")
    if objective:
        controls["si_route"] = {"objective": objective}
    return controls
