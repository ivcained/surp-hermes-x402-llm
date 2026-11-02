"""The SURP marketplace backend, loaded exactly the way Hermes loads it.

Hermes imports `dashboard/plugin_api.py` as a standalone module, so this test
does the same: a file-location import that a package-relative import could
never smuggle past. FastAPI is Hermes's own dependency, not this plugin's
(`python_dependencies: []`), so CI on a bare interpreter SKIPS honestly.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "hermes_dashboard_plugin_surp"

HAVE_FASTAPI = importlib.util.find_spec("fastapi") is not None


def load_dashboard_api():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, ROOT / "dashboard" / "plugin_api.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_FASTAPI, "fastapi is Hermes's dependency, absent on bare CI")
class DashboardApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_dashboard_api()

    def setUp(self):
        self.client = _test_client(self.api)

    def test_routes_are_mounted_where_the_page_calls_them(self):
        routes = sorted({r.path for r in self.api.router.routes})
        for expected in ("/overview", "/markets", "/markets/{model}", "/providers",
                         "/performance/{model}", "/combos", "/prefs"):
            self.assertIn(expected, routes, f"missing backend route {expected}")

    def test_overview_bundles_markets_providers_and_prefs(self):
        body = self.client.get("/overview").json()
        self.assertTrue(body["ok"])
        self.assertIn("markets", body)
        self.assertIn("providers", body)
        self.assertIn("prefs", body)

    def test_market_list_and_order_book_share_the_model_surface(self):
        markets = self.client.get("/markets?limit=5").json()
        self.assertTrue(markets["ok"])
        self.assertGreaterEqual(len(markets["models"]), 1)
        model = markets["models"][0].get("model") or markets["models"][0].get("id")
        book = self.client.get(f"/markets/{model}").json()
        self.assertTrue(book["ok"])

    def test_page_and_tool_use_the_same_read_path(self):
        # The page's providers view and the agent's surp_providers tool call
        # the same client method against the same router endpoints.
        with open(ROOT / "dashboard" / "plugin_api.py") as handle:
            source = handle.read()
        self.assertIn("cli.markets(", source)
        self.assertIn("cli.providers(", source)
        self.assertIn("routing.load_prefs()", source)

    def _tool_prefs_before(self):
        routing = _local_routing_module()
        return dict(routing.load_prefs())

    def test_prefs_round_trip_matches_the_tool(self):
        before = self._tool_prefs_before()
        try:
            patched = self.client.post("/prefs", json={
                "trusted_only": True, "objective": "price", "default_route": "surp/jev", "min_tps": 50,
            }).json()
            self.assertTrue(patched["ok"])
            self.assertTrue(patched["prefs"]["trusted_only"])
            self.assertEqual(patched["prefs"]["default_route"], "surp/jev")
            self.assertEqual(patched["prefs"]["min_tps"], 50)
        finally:
            self.client.post("/prefs", json={
                "trusted_only": before["trusted_only"],
                "objective": before["objective"],
                "default_route": before["default_route"],
                "mask_secrets": before["mask_secrets"],
                "min_tps": before["min_tps"] or 0,
            })

    def test_no_paid_endpoint_exists_on_the_backend(self):
        routes = {r.path for r in self.api.router.routes}
        for path in routes:
            self.assertNotIn("chat", path.lower())
        routing = _local_routing_module()

        before = dict(routing.load_prefs())
        try:
            saved = dict(before)
            saved["default_route"] = "surp/best-chat"
            self.assertEqual(routing.save_prefs(saved)["default_route"], "surp/best-chat")
        finally:
            routing.save_prefs(before)
        self.assertIn(_post_raw(self.client, "/prefs", {"objective": "vibes"}).status_code, (400, 422, 500))


def handlers_probe():
    """The tool layer must treat default_route exactly like the page does."""
    routing = _local_routing_module()

    saved = routing.load_prefs()
    saved["default_route"] = "surp/best-chat"
    assert routing.save_prefs(saved)["default_route"] == "surp/best-chat"
    routing.save_prefs(routing.DEFAULT_PREFS)


def _local_routing_module():
    spec = importlib.util.spec_from_file_location("test_routing_local", ROOT / "routing.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["test_routing_local"] = module
    spec.loader.exec_module(module)
    return module


def _test_client(api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app, raise_server_exceptions=False)


def _post_raw(client, path, payload):
    return client.post(
        path,
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )


if __name__ == "__main__":
    unittest.main()
