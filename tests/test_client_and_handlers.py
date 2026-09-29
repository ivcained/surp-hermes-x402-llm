import json
from unittest import mock

import pytest

import client
import handlers


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, headers=None, body=None, timeout=30):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body})
        return self.responses.pop(0)


def response(status=200, body=None, headers=None):
    return client.Response(status, headers or {}, json.dumps(body or {}).encode())


def test_public_models_needs_no_api_key():
    tx = FakeTransport([response(body={"combos": [{"combo": "best-chat"}]})])
    c = client.SurpClient("https://surp.ivc.lol", transport=tx)
    result = c.models()
    assert result["combos"][0]["combo"] == "best-chat"
    assert "Authorization" not in tx.calls[0]["headers"]


def test_chat_refuses_without_key_before_network():
    tx = FakeTransport([])
    c = client.SurpClient("https://surp.ivc.lol", transport=tx)
    with pytest.raises(client.AuthenticationRequired):
        c.chat(model="surp/best-chat", messages=[{"role": "user", "content": "hi"}])
    assert tx.calls == []


def test_chat_refuses_over_spend_ceiling_before_network():
    tx = FakeTransport([])
    c = client.SurpClient("https://surp.ivc.lol", api_key="surp_test", max_spend_usd=0.05, transport=tx)
    with pytest.raises(client.SpendLimitExceeded):
        c.chat(
            model="surp/best-chat",
            messages=[{"role": "user", "content": "hi"}],
            max_spend_usd=0.06,
            confirm_spend=True,
        )
    assert tx.calls == []


def test_paid_chat_requires_explicit_confirmation():
    tx = FakeTransport([])
    c = client.SurpClient("https://surp.ivc.lol", api_key="surp_test", transport=tx)
    with pytest.raises(client.SpendConfirmationRequired):
        c.chat(model="surp/best-chat", messages=[{"role": "user", "content": "hi"}])
    assert tx.calls == []


def test_chat_returns_cache_and_cost_metadata():
    tx = FakeTransport([
        response(
            body={"choices": [{"message": {"content": "hello"}}]},
            headers={
                "X-Surp-Cache": "HIT",
                "X-Routed-Model": "deepseek-v4-flash",
                "X-Payment-Settled": "true",
                "X-Surp-Charged-USD": "0.001",
            },
        )
    ])
    c = client.SurpClient("https://surp.ivc.lol", api_key="surp_test", transport=tx)
    result = c.chat(
        model="surp/best-chat",
        messages=[{"role": "user", "content": "hi"}],
        confirm_spend=True,
        max_spend_usd=0.01,
        temperature=0,
        stream=False,
    )
    assert result["surp"]["cache"] == "HIT"
    assert result["surp"]["routed_model"] == "deepseek-v4-flash"
    assert result["surp"]["payment_settled"] is True


def test_cacheability_explanation_matches_gateway_rules():
    good = handlers.explain_cacheability({"temperature": 0, "stream": False, "n": 1})
    assert good["cacheable"] is True
    assert good["hit_price_usd"] == 0.001

    bad = handlers.explain_cacheability({"temperature": 0.7, "stream": True, "tools": [{}]})
    assert bad["cacheable"] is False
    assert {"streaming", "nonzero_temperature", "tools"} <= set(bad["reasons"])


def test_handler_never_returns_api_key(monkeypatch):
    monkeypatch.setenv("SURP_API_KEY", "surp_secret_should_not_leak")
    tx = FakeTransport([response(body={"combos": []})])
    monkeypatch.setattr(handlers, "make_client", lambda: client.SurpClient("https://surp.ivc.lol", api_key="surp_secret_should_not_leak", transport=tx))
    result = json.loads(handlers.surp_models_handler({}, **{}))
    assert "surp_secret_should_not_leak" not in json.dumps(result)


def test_create_custom_combo_validates_locally_before_network():
    tx = FakeTransport([])
    c = client.SurpClient("https://surp.ivc.lol", transport=tx)
    with pytest.raises(client.InvalidCombo):
        c.create_combo(name="one model", models=["glm-5.2"])
    with pytest.raises(client.InvalidCombo):
        c.create_combo(name="duplicates", models=["glm-5.2", "glm-5.2"])
    assert tx.calls == []


def test_create_custom_combo_is_public_and_returns_route():
    tx = FakeTransport([response(body={
        "slug": "abc123",
        "name": "my cheap pair",
        "models": ["glm-5.2", "deepseek-v4-flash"],
        "existing": False,
        "model_id": "surp/my/abc123",
        "routes_to_now": "glm-5.2",
        "usd_per_1m_now": 0.01276,
        "pool_size": 2,
    })])
    c = client.SurpClient("https://surp.ivc.lol", transport=tx)
    result = c.create_combo(name="my cheap pair", models=["glm-5.2", "deepseek-v4-flash"])
    assert result["model_id"] == "surp/my/abc123"
    assert tx.calls[0]["method"] == "POST"
    assert tx.calls[0]["url"].endswith("/api/combos/custom")
    assert "Authorization" not in tx.calls[0]["headers"]


def test_list_and_inspect_custom_combos():
    tx = FakeTransport([
        response(body={"count": 1, "combos": [{"slug": "abc123"}]}),
        response(body={"slug": "abc123", "model_id": "surp/my/abc123", "pool": []}),
    ])
    c = client.SurpClient("https://surp.ivc.lol", transport=tx)
    assert c.custom_combos()["count"] == 1
    assert c.custom_combo("abc123")["model_id"] == "surp/my/abc123"


def test_custom_combo_handler_redacts_and_normalizes_models(monkeypatch):
    tx = FakeTransport([response(body={"model_id": "surp/my/x", "models": ["glm-5.2", "deepseek-v4-flash"]})])
    monkeypatch.setattr(handlers, "make_client", lambda: client.SurpClient("https://surp.ivc.lol", transport=tx))
    result = json.loads(handlers.surp_combo_create_handler({
        "name": "Pair",
        "models": [" GLM-5.2 ", "deepseek-v4-flash"],
    }))
    assert result["ok"] is True
    sent = json.loads(tx.calls[0]["body"])
    assert sent["models"] == ["glm-5.2", "deepseek-v4-flash"]


def test_jev_stats_is_public_and_reports_routing_telemetry():
    """surp_jev_stats needs no API key and returns the Jev routing telemetry."""

    class FakeClient:
        def jev_stats(self):
            return {
                "jev_decisions_total": 120,
                "jev_fallbacks_total": 3,
                "jev_fallback_rate": 0.025,
                "jev_shadow_agreement_rate": 0.71,
                "jev_latency_ms_p50": 388.5,
                "jev_shadow_enabled": True,
                "jev_live_enabled": True,
                "units": {"jev_latency_ms_p50": "milliseconds"},
            }

    with mock.patch.object(handlers, "make_client", return_value=FakeClient()):
        result = json.loads(handlers.surp_jev_stats_handler({}))

    assert result["ok"] is True
    assert result["jev_decisions_total"] == 120
    assert result["jev_fallback_rate"] == 0.025
    assert result["jev_shadow_agreement_rate"] == 0.71
    assert result["jev_live_enabled"] is True
