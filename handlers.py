"""Hermes tool handlers. Every handler catches failures and returns JSON."""

from __future__ import annotations

import json
from typing import Any

try:
    from . import client
except ImportError:
    import client


def make_client() -> client.SurpClient:
    return client.from_environment()


def _run(fn):
    try:
        return json.dumps(fn(), ensure_ascii=False, separators=(",", ":"))
    except client.SurpError as exc:
        return json.dumps({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"Unexpected plugin error: {exc}", "error_type": type(exc).__name__})


def surp_models_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {
        "ok": True,
        **make_client().models(
            kind=args.get("kind", "combos"),
            model_class=args.get("model_class"),
            pro=args.get("pro"),
            limit=int(args.get("limit", 100)),
        ),
    })


def surp_quote_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {
        "ok": True,
        **make_client().quote(
            model=args["model"],
            max_tokens=int(args.get("max_tokens", 1500)),
            cacheable=bool(args.get("cacheable", False)),
        ),
    })


def explain_cacheability(request: dict[str, Any] | None) -> dict[str, Any]:
    request = request or {}
    reasons = []
    if bool(request.get("stream", False)):
        reasons.append("streaming")
    if float(request.get("temperature", 0) or 0) != 0:
        reasons.append("nonzero_temperature")
    if request.get("tools"):
        reasons.append("tools")
    if int(request.get("n", 1) or 1) != 1:
        reasons.append("multiple_candidates")
    if request.get("surp_bypass_cache"):
        reasons.append("explicit_bypass")
    return {
        "cacheable": not reasons,
        "reasons": reasons,
        "ttl_minutes": 15,
        "hit_price_usd": 0.001,
        "requires_identical_request": True,
        "privacy": "The exact-cache database stores a SHA-256 request fingerprint and completed response, not the raw prompt.",
    }


def surp_cache_status_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {
        "ok": True,
        "eligibility": explain_cacheability(args.get("request")),
        "live": make_client().stats().get("response_cache", {}),
    })


def surp_chat_handler(args, **kwargs):
    args = dict(args or {})
    allowed = {
        "temperature", "max_tokens", "stream", "surp_bypass_cache", "surp_mode",
    }
    options = {k: args[k] for k in allowed if k in args}
    return _run(lambda: {
        "ok": True,
        **make_client().chat(
            model=args["model"],
            messages=args["messages"],
            confirm_spend=bool(args.get("confirm_spend", False)),
            max_spend_usd=args.get("max_spend_usd"),
            **options,
        ),
    })


def surp_usage_handler(args, **kwargs):
    return _run(lambda: {"ok": True, **make_client().usage()})


def surp_jev_stats_handler(args, **kwargs):
    return _run(lambda: {"ok": True, **make_client().jev_stats()})


def surp_combo_create_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {
        "ok": True,
        **make_client().create_combo(name=args.get("name", ""), models=args.get("models", [])),
    })


def surp_combo_list_handler(args, **kwargs):
    return _run(lambda: {"ok": True, **make_client().custom_combos()})


def surp_combo_get_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {"ok": True, **make_client().custom_combo(args.get("slug", ""))})
