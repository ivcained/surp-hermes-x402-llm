"""Minimal, dependency-free HTTP client for surp.ivc.lol."""

from __future__ import annotations

from dataclasses import dataclass
import json
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

    def _call(self, method: str, path: str, *, data=None, query=None, authenticated=False):
        if authenticated and not self.api_key:
            raise AuthenticationRequired("SURP_API_KEY is required for this operation")
        url = self.base_url + path
        if query:
            url += "?" + urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Accept": "application/json", "User-Agent": "surp-hermes-x402-llm/0.1.0"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
        body, _ = self._call("GET", "/api/keys/balance", query={"key": self.api_key}, authenticated=True)
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

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        confirm_spend: bool = False,
        max_spend_usd: float | None = None,
        **options,
    ):
        if not self.api_key:
            raise AuthenticationRequired("SURP_API_KEY is required for paid chat; surp/free may be called without it")
        if not confirm_spend:
            raise SpendConfirmationRequired("Set confirm_spend=true after reviewing the quote or spend ceiling")
        ceiling = self.max_spend_usd if max_spend_usd is None else float(max_spend_usd)
        if ceiling > self.max_spend_usd:
            raise SpendLimitExceeded(
                f"Requested ceiling ${ceiling:.4f} exceeds configured per-request limit ${self.max_spend_usd:.4f}"
            )
        payload = {"model": model, "messages": messages, **options}
        body, headers = self._call("POST", "/v1/chat/completions", data=payload, authenticated=True)
        body["surp"] = {
            "cache": headers.get("x-surp-cache", "UNKNOWN"),
            "routed_model": headers.get("x-routed-model"),
            "payment_settled": headers.get("x-payment-settled", "").lower() == "true",
            "charged_usd": _float_or_none(headers.get("x-surp-charged-usd")),
        }
        return body


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def from_environment() -> SurpClient:
    return SurpClient(
        os.getenv("SURP_BASE_URL", "https://surp.ivc.lol"),
        api_key=os.getenv("SURP_API_KEY", ""),
        max_spend_usd=float(os.getenv("SURP_MAX_SPEND_USD", "0.05")),
        timeout=int(os.getenv("SURP_TIMEOUT_SECONDS", "30")),
    )
