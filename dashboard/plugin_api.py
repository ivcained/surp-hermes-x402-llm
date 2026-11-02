"""Surp marketplace backend for the desktop page and dashboard tab.

Mounted by Hermes at /api/plugins/surp-hermes-x402-llm/ (mirrored on the web
dashboard). Every handler is a thin wrapper around the SAME modules the agent's
tools use (`client`, `handlers`, `routing`), so the page and the agent can
never drift apart.

Security boundaries, mirroring the tool layer:
- Read-only, public Surp endpoints are served directly (markets, providers,
  performance, combos). No key ever leaves the server.
- The paid chat path is NOT exposed here. Pressing "Send" on the page writes
  a drafted request into the chat composer; the user reviews and sends it, and
  the agent's surp_chat tool (plus the pre_tool_call approval gate) applies
  the same protections as always.
- Route preferences are stored per profile exactly like the tool layer
  (routing.py load/save), so the page and the agent share one source of truth.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _plugin_module(name: str) -> Any:
    """Load one of the plugin's own modules, whatever the folder is called."""
    package = _PLUGIN_ROOT.name
    if package not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package, _PLUGIN_ROOT / "__init__.py", submodule_search_locations=[str(_PLUGIN_ROOT)]
        )
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise ImportError(f"cannot load the {package} plugin package")
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        spec.loader.exec_module(module)
    return importlib.import_module(f"{package}.{name}")


def _client_and_prefs() -> tuple[Any, Any]:
    client = _plugin_module("client")
    routing = _plugin_module("routing")
    return client.from_environment(), routing


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


class PrefsPatch(BaseModel):
    trusted_only: bool | None = None
    block_providers: list[str] | None = None
    prefer_providers: list[str] | None = None
    objective: str | None = None
    mask_secrets: bool | None = None
    default_route: str | None = None
    min_tps: float | None = Field(default=None, ge=0, le=100000)
    min_discount: int | None = Field(default=None, ge=0, le=100)


@router.get("/overview")
def get_overview() -> dict[str, Any]:
    """Markets + providers + current route prefs in one call for the first paint."""
    cli, routing = _client_and_prefs()
    markets = cli.markets(limit=500)
    providers = cli.providers()
    return _ok(markets=markets, providers=providers, prefs=routing.load_prefs())


@router.get("/markets")
def get_markets(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """Every model with best price, seller count and volume."""
    cli, _ = _client_and_prefs()
    return _ok(**cli.markets(limit=limit))


@router.get("/markets/{model}")
def get_order_book(model: str) -> dict[str, Any]:
    """One model's full order book (every offer: price, capacity, health, provider)."""
    cli, _ = _client_and_prefs()
    return _ok(**cli.markets(model=model))


@router.get("/combos")
def get_combos() -> dict[str, Any]:
    """Public routing combos for the default-route picker."""
    cli, _ = _client_and_prefs()
    return _ok(**cli.models(kind="combos"))


@router.get("/providers")
def get_providers() -> dict[str, Any]:
    """Provider catalog: trusted flags plus live TPS / TTFT / latency / uptime."""
    cli, _ = _client_and_prefs()
    return _ok(**cli.providers())


@router.get("/performance/{model}")
def get_performance(model: str) -> dict[str, Any]:
    """Per-model provider performance (same data the surp_providers tool reads)."""
    cli, _ = _client_and_prefs()
    return _ok(**cli.providers(model=model))


@router.get("/composer/market")
def get_composer_market(model: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
    """Selected-model provider choices for the composer's TPS/price controls."""
    cli, routing = _client_and_prefs()
    return _ok(board=cli.seller_board(model=model.strip()), prefs=routing.load_prefs())


@router.get("/prefs")
def get_prefs() -> dict[str, Any]:
    """Current route preferences — the single source of truth shared with the agent."""
    _, routing = _client_and_prefs()
    return _ok(prefs=routing.load_prefs())


@router.post("/prefs")
def set_prefs(patch: PrefsPatch) -> dict[str, Any]:
    """Change route preferences the same way surp_route_prefs does."""
    routing = _plugin_module("routing")
    current = routing.load_prefs()
    data = patch.model_dump(exclude_none=True)
    for key in ("trusted_only", "mask_secrets"):
        if key in data:
            current[key] = bool(data[key])
    for key in ("block_providers", "prefer_providers"):
        if key in data:
            current[key] = [str(x) for x in data[key]]
    if "objective" in data:
        current["objective"] = data["objective"]
    if data.get("default_route"):
        current["default_route"] = data["default_route"]
    if "min_tps" in data:
        current["min_tps"] = data["min_tps"]
    if "min_discount" in data:
        current["min_discount"] = data["min_discount"]
    return _ok(action="set", prefs=routing.save_prefs(current))
