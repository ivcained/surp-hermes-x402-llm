"""Hermes tool handlers. Every handler catches failures and returns JSON."""

from __future__ import annotations

import json
from typing import Any

try:
    from . import client
    from . import routing as route_prefs
except ImportError:
    import client
    import routing as route_prefs


_plugin_ctx = None

# Short in-process cache of the provider list so trusted_only resolution does
# not re-fetch the catalog on every chat call.
_providers_cache = {"at": 0.0, "rows": None}
_PROVIDERS_TTL = 60.0


def set_context(ctx) -> None:
    """Remember the Hermes plugin context so config.yaml settings are read at call time."""
    global _plugin_ctx
    _plugin_ctx = ctx
    # Invalidate the provider cache when a new context arrives (profile switch).
    _providers_cache["at"] = 0.0
    _providers_cache["rows"] = None


def make_client() -> client.SurpClient:
    return client.from_environment(getattr(_plugin_ctx, "get_config", None))


def _untrusted_providers(cli: client.SurpClient) -> list[str]:
    """Providers without the trusted flag, for trusted_only routing."""
    import time

    now = time.monotonic()
    if _providers_cache["rows"] is None or now - _providers_cache["at"] > _PROVIDERS_TTL:
        _providers_cache["rows"] = cli.providers().get("providers", [])
        _providers_cache["at"] = now
    return [
        str(row.get("provider") or row.get("id") or row.get("name") or "").strip().lower()
        for row in _providers_cache["rows"]
        if not bool(row.get("trusted"))
    ]


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

    def _chat():
        cli = make_client()
        prefs = route_prefs.load_prefs()
        # One-request overrides win over saved preferences.
        blocked = list(prefs.get("block_providers") or [])
        if args.get("providers_blocked") is not None:
            blocked = [str(p).strip().lower() for p in args["providers_blocked"] if str(p).strip()]
        prefer = list(prefs.get("prefer_providers") or [])
        if args.get("provider_order") is not None:
            prefer = [str(p).strip().lower() for p in args["provider_order"] if str(p).strip()]
        objective = prefs.get("objective")
        if args.get("si_objective"):
            objective = str(args["si_objective"])
        mask_secrets = bool(prefs.get("mask_secrets"))
        if args.get("mask_secrets") is not None:
            mask_secrets = bool(args["mask_secrets"])
        if prefs.get("trusted_only") and args.get("providers_blocked") is None:
            for name in _untrusted_providers(cli):
                if name and name not in blocked:
                    blocked.append(name)
        routing = {}
        if blocked:
            routing["providers_blocked"] = blocked
        if prefer:
            routing["provider_order"] = prefer
        if objective:
            routing["si_route"] = {"objective": objective}
        result = cli.chat(
            model=args["model"],
            messages=args["messages"],
            confirm_spend=bool(args.get("confirm_spend", False)),
            max_spend_usd=args.get("max_spend_usd"),
            routing=routing or None,
            mask_secrets=mask_secrets,
            **options,
        )
        result["surp"]["routing_applied"] = routing or None
        result["surp"]["mask_secrets"] = mask_secrets
        return result

    return _run(lambda: {"ok": True, **_chat()})


def surp_markets_handler(args, **kwargs):
    args = args or {}
    model = args.get("model")
    return _run(lambda: {
        "ok": True,
        **make_client().markets(
            model=model,
            limit=int(args.get("limit", 100)),
        ),
    })


def surp_providers_handler(args, **kwargs):
    args = args or {}
    return _run(lambda: {
        "ok": True,
        **make_client().providers(
            model=args.get("model"),
            include_performance=bool(args.get("include_performance", True)),
        ),
    })


def surp_route_prefs_handler(args, **kwargs):
    args = args or {}

    def _prefs():
        action = args.get("action", "get")
        if action == "reset":
            return {"ok": True, "action": "reset", "prefs": route_prefs.save_prefs(dict(route_prefs.DEFAULT_PREFS))}
        if action == "get":
            return {"ok": True, "action": "get", "prefs": route_prefs.load_prefs()}
        if action != "set":
            raise client.SurpError("action must be one of get, set, reset")
        current = route_prefs.load_prefs()
        for key in ("trusted_only", "mask_secrets"):
            if args.get(key) is not None:
                current[key] = bool(args[key])
        for key in ("block_providers", "prefer_providers"):
            if args.get(key) is not None:
                current[key] = args[key]
        if args.get("objective") is not None:
            current["objective"] = args["objective"]
        saved = route_prefs.save_prefs(current)
        # Drop the in-process provider cache so a trusted_only flip re-reads the catalog.
        _providers_cache["at"] = 0.0
        _providers_cache["rows"] = None
        return {"ok": True, "action": "set", "prefs": saved}

    return _run(_prefs)


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
