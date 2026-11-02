"""Minimal, dependency-free HTTP client for surp.ivc.lol."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SurpError(RuntimeError):
    pass


class AuthenticationRequired(SurpError):
    pass


class SpendConfirmationRequired(SurpError):
    pass


class SpendLimitExceeded(SurpError):
    pass


class TpsFloorUnavailable(SurpError):
    pass


class InvalidCombo(SurpError):
    pass


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict[str, Any]:
        try:
            return json.loads(self.body.decode("utf-8"))
        except Exception as exc:
            raise SurpError(f"Surp returned non-JSON data (HTTP {self.status})") from exc


class UrllibTransport:
    def request(self, method, url, *, headers=None, body=None, timeout=30) -> Response:
        request = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=timeout) as result:
                return Response(result.status, dict(result.headers.items()), result.read())
        except HTTPError as exc:
            return Response(exc.code, dict(exc.headers.items()), exc.read())
        except URLError as exc:
            raise SurpError(f"Could not reach Surp: {exc.reason}") from exc


class SurpClient:
    def __init__(
        self,
        base_url: str = "https://surp.ivc.lol",
        *,
        api_key: str | None = None,
        max_spend_usd: float = 0.05,
        timeout: int = 30,
        transport=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.max_spend_usd = float(max_spend_usd)
        self.timeout = int(timeout)
        self.transport = transport or UrllibTransport()

    def _call(
        self,
        method: str,
        path: str,
        *,
        data=None,
        query=None,
        authenticated=False,
        extra_headers: dict[str, str] | None = None,
    ):
        if authenticated and not self.api_key:
            raise AuthenticationRequired("SURP_API_KEY is required for this operation")
        url = self.base_url + path
        if query:
            url += "?" + urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Accept": "application/json", "User-Agent": "surp-hermes-x402-llm/0.8.0"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra_headers:
            headers.update({k: v for k, v in extra_headers.items() if v})
        raw = None
        if data is not None:
            raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        response = self.transport.request(method, url, headers=headers, body=raw, timeout=self.timeout)
        body = response.json()
        if response.status >= 400:
            message = body.get("error") or body.get("detail") or f"HTTP {response.status}"
            raise SurpError(str(message))
        return body, {k.lower(): v for k, v in response.headers.items()}

    def models(self, *, kind="combos", model_class=None, pro=None, limit=100):
        if kind == "combos":
            body, _ = self._call("GET", "/api/combos")
            return body
        body, _ = self._call("GET", "/api/models")
        rows = body.get("models", [])
        if model_class:
            rows = [row for row in rows if row.get("class") == model_class]
        if pro is not None:
            rows = [row for row in rows if bool(row.get("pro")) is bool(pro)]
        return {"count": len(rows[:limit]), "models": rows[:limit]}

    def stats(self):
        body, _ = self._call("GET", "/api/stats")
        return body

    def markets(self, *, model: str | None = None, limit: int = 100):
        """Live Surplus Intelligence market data.

        Without ``model``: every model with its best price, seller count and
        volume. With ``model``: that model's full order book (every offer with
        price, capacity, health, provider). Public and free.
        """
        clean = (str(model or "").strip().lower()) or None
        if clean and any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-/" for ch in clean):
            raise SurpError("Invalid model id for market lookup")
        path = f"/api/markets/{clean}" if clean else "/api/markets"
        body, _ = self._call("GET", path)
        if clean:
            return body
        models = body.get("models") or body.get("markets") or (body if isinstance(body, list) else [])
        rows = [row for row in models if isinstance(row, dict) and (row.get("model") or row.get("id"))][: max(1, min(int(limit), 500))]
        return {"count": len(rows), "models": rows, "cached": bool(body.get("cached")) if isinstance(body, dict) else None}

    def providers(self, *, model: str | None = None, include_performance: bool = True):
        """Provider catalog with trusted flags and, when available, live TPS.

        Aggregates per provider by default; per-model performance rows when
        ``model`` is given. Public and free.
        """
        if model:
            clean = str(model).strip().lower()
            body, _ = self._call("GET", f"/api/performance/{clean}")
            return _with_tps_summary(body)
        body, _ = self._call("GET", "/api/providers")
        providers = body.get("providers", body if isinstance(body, list) else [])
        rows = [row for row in providers if isinstance(row, dict)]
        if include_performance is False:
            rows = [
                {k: v for k, v in row.items() if k not in ("tps_p50", "tps", "avg_latency_ms", "uptime_pct")}
                for row in rows
            ]
            return {"count": len(rows), "providers": rows}
        return _with_tps_summary({"count": len(rows), "providers": rows})

    def seller_board(self, *, model: str) -> dict[str, Any]:
        """Cheapest and fastest provider choices for one model, with live discounts.

        Prices and direct-list references come from the current order book. TPS,
        TTFT and uptime are trailing-24h measurements when SI has them. Missing
        performance data never hides the price/discount choices.
        """
        book = self.markets(model=model)
        market = book.get("market") if isinstance(book.get("market"), dict) else book
        market = market or {}
        try:
            performance = self.providers(model=market.get("model") or model)
            performance_rows = performance.get("providers", [])
            performance_error = None
            average_tps = performance.get("average_tps")
        except SurpError as exc:
            performance_rows = []
            performance_error = str(exc)
            average_tps = None
        perf = {
            str(row.get("provider") or "").strip().lower(): row
            for row in performance_rows
            if isinstance(row, dict) and row.get("provider")
        }
        direct_total = sum(
            float(market.get(key) or 0)
            for key in ("direct_input_per_1m", "direct_output_per_1m")
        )
        rows = []
        for source in market.get("providers") or book.get("providers") or []:
            if not isinstance(source, dict) or not source.get("provider"):
                continue
            name = str(source["provider"]).strip().lower()
            row = dict(source)
            measured = perf.get(name) or {}
            for key in ("tps_p50", "ttft_p50_ms", "uptime_pct"):
                row[key] = measured.get(key)
            price = _float_or_none(source.get("best_price_per_1m"))
            row["price_usd_per_1m"] = price / 1_000_000 if price is not None else None
            row["discount_pct"] = (
                round(max(0.0, 100 * (1 - price / direct_total)), 2)
                if price is not None and direct_total > 0 else None
            )
            rows.append(row)
        cheapest = sorted(rows, key=lambda row: row["price_usd_per_1m"] if row["price_usd_per_1m"] is not None else float("inf"))
        fastest = sorted(rows, key=lambda row: row["tps_p50"] if row["tps_p50"] is not None else -1, reverse=True)
        return {
            "model": market.get("model") or book.get("model") or model,
            "providers": rows,
            "cheapest": cheapest[:5],
            "fastest": fastest[:5],
            "average_tps": average_tps,
            "best_discount_pct": market.get("best_discount_pct"),
            "performance_error": performance_error,
            "discount_basis": "estimated buyer discount vs direct input+output list prices",
        }

    def jev_stats(self):
        """Jev routing telemetry: decisions, fallback rate, agreement rate, latency."""
        body, _ = self._call("GET", "/api/jev/stats")
        return body

    def create_combo(self, *, name: str, models: list[str]):
        clean_name = str(name or "").strip()
        clean_models = [str(model).strip().lower() for model in (models or []) if str(model).strip()]
        if len(clean_models) < 2 or len(clean_models) > 20:
            raise InvalidCombo("A custom combo requires 2 to 20 model ids")
        if len(set(clean_models)) != len(clean_models):
            raise InvalidCombo("Custom combo model ids must be unique")
        if len(clean_name) > 80:
            raise InvalidCombo("Custom combo name must be 80 characters or fewer")
        body, _ = self._call("POST", "/api/combos/custom", data={"name": clean_name, "models": clean_models})
        return body

    def custom_combos(self):
        body, _ = self._call("GET", "/api/combos/custom")
        return body

    def custom_combo(self, slug: str):
        clean = str(slug or "").strip().lower()
        if not clean or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in clean):
            raise InvalidCombo("Invalid custom combo slug")
        body, _ = self._call("GET", f"/api/combos/custom/{clean}")
        return body

    def usage(self):
        body, _ = self._call("GET", "/api/keys/balance", authenticated=True)
        return body

    def quote(self, *, model: str, max_tokens: int = 1500, cacheable: bool = False):
        combos = self.models(kind="combos").get("combos", [])
        normalized = model if model.startswith("surp/") else f"surp/{model}"
        row = next((x for x in combos if x.get("combo") == normalized), None)
        if row is None:
            raise SurpError(f"Unknown or unavailable Surp combo: {normalized}")
        fresh = max(0.01, float(row.get("usd_per_1m_tokens", 0)) * max_tokens / 1_000_000 * 1.05)
        return {
            "model": normalized,
            "resolved_model": row.get("resolved_model"),
            "expected_tokens": max_tokens,
            "fresh_estimate_usd": round(fresh, 6),
            "exact_cache_hit_usd": 0.001 if cacheable else None,
            "note": "A cache hit is possible only for an identical eligible request already stored within the 15-minute TTL.",
        }

    def _estimate_usd(self, model: str, max_tokens: int) -> float:
        """Live price for max_tokens on this route (same formula as quote()).

        Custom combos are priced at their most expensive member, since the
        route can change between this check and the request.
        """
        normalized = model if model.startswith("surp/") else f"surp/{model}"
        if not normalized.startswith("surp/my/"):
            return float(self.quote(model=model, max_tokens=max_tokens)["fresh_estimate_usd"])
        pool = self.custom_combo(normalized[len("surp/my/"):]).get("pool") or []
        prices = [float(row.get("usd_per_1m", 0) or 0) for row in pool]
        if not prices:
            raise SurpError(f"Cannot price custom combo {normalized}; refusing paid request")
        return max(0.01, max(prices) * max_tokens / 1_000_000 * 1.05)

    def _routing_with_tps_floor(
        self, routing: dict[str, Any] | None, min_tps: float, resolved_model: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Block current providers below the resolved model's trailing-24h p50 TPS.

        This is a preference filter, not a throughput guarantee. It runs before
        the paid request and never retries an in-flight request automatically.
        """
        floor = float(min_tps)
        if not math.isfinite(floor) or floor <= 0:
            raise SurpError("min_tps must be greater than 0 when enabled")
        controls = dict(routing or {})
        blocked = [str(p).strip().lower() for p in controls.get("providers_blocked", []) if str(p).strip()]
        performance = self.providers(model=resolved_model)
        performance_by_name = {
            str(row.get("provider") or "").strip().lower(): row
            for row in performance.get("providers", [])
            if row.get("provider")
        }
        book = self.markets(model=resolved_model)
        market = book.get("market") if isinstance(book.get("market"), dict) else book
        market = market or {}
        current_rows = market.get("providers") or book.get("offers") or []
        current_names = {
            str(row.get("provider") or "").strip().lower()
            for row in current_rows
            if isinstance(row, dict) and row.get("provider")
        }
        # Current offers decide eligibility; performance supplies the metric.
        # If an older router omits the offer providers, use performance rows.
        candidate_names = current_names or set(performance_by_name)
        eligible = []
        for name in sorted(candidate_names):
            row = performance_by_name.get(name) or {}
            tps = _float_or_none(row.get("tps_p50"))
            if tps is not None and tps >= floor and name not in blocked:
                eligible.append({"provider": name, "tps_p50": tps})
            elif name not in blocked:
                # Missing measurements do not qualify for a user-set floor.
                blocked.append(name)
        if not eligible:
            raise TpsFloorUnavailable(
                f"No current unblocked provider for {resolved_model} meets the {floor:g} TPS floor. "
                "Lower or clear min_tps, or change trusted/blocked provider preferences; no paid request was sent."
            )
        controls["providers_blocked"] = blocked
        eligible.sort(key=lambda row: row["tps_p50"], reverse=True)
        return controls, {
            "min_tps": floor,
            "resolved_model": resolved_model,
            "basis": "current providers for the quoted route, trailing-24h p50; missing/slower measurements excluded before payment",
            "eligible_providers": eligible,
        }

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        confirm_spend: bool = False,
        max_spend_usd: float | None = None,
        routing: dict[str, Any] | None = None,
        mask_secrets: bool = False,
        min_tps: float | None = None,
        min_discount: int = 0,
        **options,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise AuthenticationRequired("SURP_API_KEY is required for paid chat; surp/free may be called without it")
        if not confirm_spend:
            raise SpendConfirmationRequired("Set confirm_spend=true after reviewing the quote or spend ceiling")
        ceiling = self.max_spend_usd if max_spend_usd is None else float(max_spend_usd)
        if ceiling > self.max_spend_usd:
            raise SpendLimitExceeded(
                f"Requested ceiling ${ceiling:.4f} exceeds configured per-request limit ${self.max_spend_usd:.4f}"
            )
        # Surp prices a request up front from max_tokens, so pin it and refuse
        # before the paid call when that price is above the ceiling.
        options.setdefault("max_tokens", 1500)
        normalized = model if model.startswith("surp/") else f"surp/{model}"
        resolved_model = None
        if normalized.startswith("surp/my/"):
            estimate = self._estimate_usd(model, int(options["max_tokens"]))
        else:
            quote = self.quote(model=model, max_tokens=int(options["max_tokens"]))
            estimate = float(quote["fresh_estimate_usd"])
            resolved_model = quote.get("resolved_model")
        if estimate > ceiling:
            raise SpendLimitExceeded(
                f"Estimated cost ${estimate:.4f} for max_tokens={options['max_tokens']} exceeds the "
                f"${ceiling:.4f} per-request ceiling; the request was not sent (lower max_tokens)"
            )
        tps_routing = None
        if min_tps is not None:
            if not resolved_model:
                raise SurpError(
                    "min_tps requires a built-in combo with a currently resolved model; "
                    "custom combos cannot be TPS-filtered safely. No paid request was sent."
                )
            routing, tps_routing = self._routing_with_tps_floor(routing, min_tps, resolved_model)
        payload = {"model": model, "messages": messages, **options}
        if routing:
            # Surplus Intelligence routing controls: providers_blocked,
            # provider_order, si_route objective. Unknown keys are refused
            # upstream anyway, so only forward documented ones.
            for key in ("providers_blocked", "provider_order", "si_route"):
                if routing.get(key) is not None:
                    payload[key] = routing[key]
        extra_headers = {"X-SI-Mask-Secrets": "on"} if mask_secrets else {}
        discount = int(min_discount or 0)
        if discount < 0 or discount > 100:
            raise SurpError("min_discount must be an integer from 0 to 100")
        if discount:
            extra_headers["X-Min-Discount"] = str(discount)
        body, headers = self._call(
            "POST", "/v1/chat/completions", data=payload, authenticated=True, extra_headers=extra_headers
        )
        body["surp"] = {
            "cache": headers.get("x-surp-cache", "UNKNOWN"),
            "routed_model": headers.get("x-routed-model"),
            "payment_settled": headers.get("x-payment-settled", "").lower() == "true",
            "charged_usd": _float_or_none(headers.get("x-surp-charged-usd")),
            "served_by": headers.get("x-si-served-by"),
            "marketplace_attempts": headers.get("x-si-marketplace-attempts"),
            "failed_attempts": headers.get("x-si-attempts") or None,
            "buyer_cost_usd": _micro_to_usd(headers.get("x-si-buyer-cost-micro")),
            "truncated": headers.get("x-si-truncated") == "1",
            "secret_masking": headers.get("x-si-secret-masking"),
            "tps_routing": tps_routing,
            "routing_controls": routing or None,
            "min_discount": discount,
        }
        return body


def _with_tps_summary(body: dict[str, Any]) -> dict[str, Any]:
    """Add the arithmetic mean of reported provider p50 TPS values."""
    result = dict(body)
    rows = result.get("providers") or []
    samples = [
        value
        for value in (_float_or_none(row.get("tps_p50")) for row in rows if isinstance(row, dict))
        if value is not None
    ]
    result["average_tps"] = round(sum(samples) / len(samples), 1) if samples else None
    result["tps_provider_count"] = len(samples)
    result["tps_summary_basis"] = "arithmetic mean of provider p50 TPS measurements"
    return result


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _micro_to_usd(value):
    try:
        return round(int(value) / 1_000_000, 6)
    except (TypeError, ValueError):
        return None


def _surp_api_key() -> str:
    """SURP_API_KEY through Hermes' profile-scoped secret store (agent.secret_scope),
    never a bare os.environ/.env read — catalog rule: declared env secrets resolve
    through the scope so multiplexed profiles never leak each other's keys. The
    scope itself falls back to the process env on single-profile deployments."""
    try:
        from agent.secret_scope import get_secret_str
        return (get_secret_str("SURP_API_KEY", "") or "").strip()
    except Exception:
        return ""


def from_environment(get_config=None) -> SurpClient:
    """Build a client from config.yaml plugin settings, falling back to SURP_* env vars.

    ``get_config`` is Hermes' ``ctx.get_config(key, default)``. If both config.yaml
    and SURP_MAX_SPEND_USD set a spend ceiling, the lower one applies.
    """
    get = get_config or (lambda key, default=None: default)
    limits = [float(v) for v in (get("max_spend_usd", None), os.getenv("SURP_MAX_SPEND_USD")) if v not in (None, "")]
    return SurpClient(
        get("base_url", None) or os.getenv("SURP_BASE_URL", "https://surp.ivc.lol"),
        api_key=_surp_api_key(),
        max_spend_usd=min(limits) if limits else 0.05,
        timeout=int(get("timeout_seconds", None) or os.getenv("SURP_TIMEOUT_SECONDS", "30")),
    )
