import json

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
