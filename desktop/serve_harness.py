#!/usr/bin/env python3
"""Preview harness: serve the SURP desktop page with a live backend in a real browser.

Serves desktop/harness.html plus two mounts:
  /surp-page/plugin.js  — the real desktop/plugin.js, with imports rewritten to the harness shims
  /surp-api/*           — the real dashboard/plugin_api.py backend (live surp.ivc.lol data)

Run:  .venv/bin/python desktop/serve_harness.py
Then open http://127.0.0.1:8471/ and screenshot the Prices, Providers and Router tabs.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PORT = 8471


def load_backend():
    spec = importlib.util.spec_from_file_location(
        "harness_backend", ROOT / "dashboard" / "plugin_api.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["harness_backend"] = module
    spec.loader.exec_module(module)
    return module


PLUGIN_SRC = (ROOT / "desktop" / "plugin.js").read_text()


def shimmed_plugin():
    """Rewrite the plugin's bare imports to the harness's shim modules."""
    src = PLUGIN_SRC.replace("from '@hermes/plugin-sdk'", "from '/shim/sdk.js'")
    src = src.replace("from 'react'", "from '/shim/react.js'")
    src = src.replace("from 'react/jsx-runtime'", "from '/shim/jsx.js'")
    return src


def main():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    backend = load_backend()
    harness_html = (ROOT / "desktop" / "harness.html").read_text()
    shim_dir = ROOT / "desktop" / "harness-shims"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, body: bytes, ctype="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(harness_html.encode(), "text/html; charset=utf-8")
            elif parsed.path == "/surp-page/plugin.js":
                self._send(shimmed_plugin().encode(), "text/javascript")
            elif parsed.path.startswith("/shim/"):
                self._send((shim_dir / parsed.path[len("/shim/"):]).read_bytes(), "text/javascript")
            elif parsed.path.startswith("/surp-api/"):
                try:
                    sub = parsed.path[len("/surp-api"):] or "/"
                    result = _call_backend(backend, "GET", sub, None)
                    self._send(json.dumps(result).encode())
                except Exception as exc:  # keep the harness honest: surface, don't hide
                    self._send(json.dumps({"ok": False, "error": str(exc)[:300]}).encode(), code=500)
            else:
                self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0) or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if parsed.path.startswith("/surp-api/"):
                sub = parsed.path[len("/surp-api"):] or "/"
                try:
                    result = _call_backend(backend, "POST", sub, payload)
                    self._send(json.dumps(result).encode())
                except Exception as exc:
                    self._send(json.dumps({"ok": False, "error": str(exc)[:300]}).encode(), code=500)
            else:
                self._send(b"not found", "text/plain", 404)

    httpd = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"serving harness on http://127.0.0.1:{PORT}/", flush=True)
    httpd.serve_forever()


def _call_backend(backend, method, sub, payload):
    path, _, query = sub.partition("?")
    params = dict(kv.split("=", 1) for kv in query.split("&") if "=" in kv) if query else {}
    if path == "/overview" and method == "GET":
        return backend.get_overview()
    if path == "/markets" and method == "GET":
        return backend.get_markets(limit=int(params.get("limit", 100)))
    if path.startswith("/markets/") and method == "GET":
        return backend.get_order_book(path[len("/markets/"):])
    if path == "/providers" and method == "GET":
        return backend.get_providers()
    if path.startswith("/performance/") and method == "GET":
        return backend.get_performance(path[len("/performance/"):])
    if path == "/combos" and method == "GET":
        return backend.get_combos()
    if path == "/prefs" and method == "GET":
        return backend.get_prefs()
    if path == "/prefs" and method == "POST":
        return backend.set_prefs(backend.PrefsPatch(**payload))
    raise ValueError(f"no harness route for {method} {sub}")


if __name__ == "__main__":
    main()
