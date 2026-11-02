"""Persistent per-profile routing preferences for Surp chat requests.

The user can flip these mid-conversation with the ``surp_route_prefs`` tool;
they are merged into every ``surp_chat`` call as Surplus Intelligence routing
controls (``providers_blocked``, ``provider_order``, ``si_route``) and the
``X-SI-Mask-Secrets`` header.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

DEFAULT_PREFS = {
    "trusted_only": False,
    "block_providers": [],
    "prefer_providers": [],
    "objective": None,  # "price" | "latency" | "balanced" | None (router default)
    "mask_secrets": False,
    "default_route": None,  # surp combo id the user picked as their default route
    "min_tps": None,  # trailing-24h p50 floor for the current resolved model
    "min_discount": 0,  # SI minimum estimated buyer discount vs external list price
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
    route = prefs.get("default_route")
    clean["default_route"] = str(route).strip() if isinstance(route, str) and route.strip() else None
    raw_min_tps = prefs.get("min_tps")
    if raw_min_tps in (None, "", 0, "0"):
        clean["min_tps"] = None
    else:
        if isinstance(raw_min_tps, bool):
            raise ValueError("min_tps must be a non-negative number")
        try:
            min_tps = float(raw_min_tps)
        except (TypeError, ValueError) as exc:
            raise ValueError("min_tps must be a non-negative number") from exc
        if not math.isfinite(min_tps) or min_tps < 0 or min_tps > 100000:
            raise ValueError("min_tps must be between 0 and 100000 tokens/second")
        clean["min_tps"] = min_tps
    raw_discount = prefs.get("min_discount", 0)
    if raw_discount in (None, ""):
        raw_discount = 0
    if isinstance(raw_discount, bool):
        raise ValueError("min_discount must be an integer from 0 to 100")
    try:
        discount = float(raw_discount)
    except (TypeError, ValueError) as exc:
        raise ValueError("min_discount must be an integer from 0 to 100") from exc
    if not math.isfinite(discount) or discount < 0 or discount > 100 or not discount.is_integer():
        raise ValueError("min_discount must be an integer from 0 to 100")
    clean["min_discount"] = int(discount)
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
