# surp-hermes-x402-llm

Standalone Hermes Agent plugin for Surp's Jev-integrated smart LLM router.

Surp routes OpenAI-compatible requests across live models with x402 payments on Base. Route selection is backed by [Jev](https://typesafe.ai), TypeSafe's System One decision model: per request, Jev scores a bounded candidate list against price, latency, cache state, and route health, with a confidence score and fail-open fallback to static routing. Prompt content never leaves the router — Jev sees request metadata only. The opt-in `surp/jev` preset follows Jev's pick; the other presets stay static.

It adds twelve tools:

- `surp_models` — inspect live combos or models
- `surp_markets` — current marketplace prices for all models (best price, sellers, volume; or one model's full order book)
- `surp_providers` — every provider's trusted flag plus live TPS, TTFT, latency and uptime; per-model provider performance with `model`
- `surp_route_prefs` — switch trusted/untrusted sellers, pin or block providers, set the routing objective, and turn secret masking on — mid-chat, without config edits
- `surp_quote` — estimate fresh inference and the exact-cache tier without spending
- `surp_cache_status` — check cache eligibility and public cache metrics
- `surp_chat` — guarded OpenAI-compatible chat using a Surp API key; applies routing preferences and secret masking automatically
- `surp_usage` — inspect configured-key balance and usage
- `surp_jev_stats` — Jev decision-model routing telemetry: decisions, fallback rate, shadow agreement rate, p50 latency
- `surp_combo_create` — create or reuse a public combo from 2–20 models
- `surp_combo_list` — browse community-created combos
- `surp_combo_get` — inspect one combo's pool and current route

The bundled `surp` skill teaches Hermes how to choose routes, quote before spending, build cache-friendly requests, interpret payment metadata, read market prices and provider TPS, switch sellers, and mask secrets.

## Marketplace visibility and seller switching

- `surp_markets` (free, no key): every model's live best price, seller count and volume; pass a model id for its full order book — every offer with price, capacity remaining, health status and provider.
- `surp_providers` (free, no key): the provider catalog with each provider's `trusted` flag and live throughput — TPS (p50), TTFT, latency and uptime. Pass a model for per-model rows.
- `surp_route_prefs`: persistent per-profile routing preferences applied to every `surp_chat` call:
  - `trusted_only` — route only to providers on Surplus Intelligence's trusted allowlist;
  - `block_providers` / `prefer_providers` — block or pin specific sellers;
  - `objective` — `price`, `latency` or `balanced`;
  - `mask_secrets` — send `X-SI-Mask-Secrets: on` so secrets in the prompt (API keys, private keys, passwords) are replaced with placeholders before the request reaches the seller and restored in the response.
  
  Preferences are stored per profile under `$HERMES_HOME/cache/surp-hermes-x402-llm/route-prefs.json` and take effect on the next call — mid-conversation switching with no restart.
- `surp_chat` accepts one-request overrides (`providers_blocked`, `provider_order`, `si_objective`, `mask_secrets`) and reports what was applied in `surp.routing_applied`, plus settlement metadata: `surp.served_by`, `surp.failed_attempts`, `surp.buyer_cost_usd`, `surp.truncated`, `surp.secret_masking`.

## Install

```bash
hermes plugins install ivcained/surp-hermes-x402-llm --no-enable
hermes plugins enable surp-hermes-x402-llm
hermes plugins doctor surp-hermes-x402-llm --ci
```

Public model, quote, and cache tools work without credentials. For paid chat and usage, store a key in Hermes' secret environment:

```bash
hermes config set-secret SURP_API_KEY
```

If your Hermes version does not provide `set-secret`, add `SURP_API_KEY` to `~/.hermes/.env` manually. Do not put keys in `config.yaml`, prompts, or tool arguments.

Behavioral settings belong in `config.yaml` under the plugin entry:

```yaml
plugins:
  entries:
    surp-hermes-x402-llm:
      settings:
        base_url: https://surp.ivc.lol
        max_spend_usd: 0.05
        timeout_seconds: 30
```

These settings are read at call time. `SURP_BASE_URL`, `SURP_MAX_SPEND_USD`, and `SURP_TIMEOUT_SECONDS` are still accepted as fallbacks; if both `config.yaml` and `SURP_MAX_SPEND_USD` set a ceiling, the lower one applies. The API key is the only required secret.

## Jev smart routing

Surp integrates [Jev](https://typesafe.ai), TypeSafe's System One decision model, as an optional routing brain. Instead of a static quality/cost table alone, Jev evaluates each request's envelope — token estimate, modality, route health, cache state, latency percentiles — and scores each candidate route from a bounded list.

- Opt in with `model: "surp/jev"`. Other presets stay static.
- Jev receives request metadata only, never prompt content.
- Each pick carries a confidence score; below threshold, the static router takes over.
- Jev timeout, error, or low confidence falls open to the existing router. Availability never depends on Jev.
- Ships first as shadow telemetry (logging what Jev would have picked), then as the live preset.

## Payment boundary

Version 0.5 routes every paid request through Hermes' human-approval gate. A `pre_tool_call` hook escalates any `surp_chat` call with `confirm_spend: true` to the same approval prompt machinery as dangerous shell commands: the user — not the model — authorizes the spend (once / session / always / deny; gateway users get a pending-approval card). The approval grain is per model, so "always" on one model never covers another. Unattended contexts (cron, single-query `-q` runs) fail closed by default — the paid call is denied, never silently sent. `approvals.mode: off` and YOLO bypass the prompt, exactly like every other Hermes approval.

Before the paid call, the plugin also prices the request the way Surp does (live route price × `max_tokens`, default 1500, plus markup) and refuses it if that price exceeds the ceiling. `max_tokens` is always sent, so Surp prices the request from that same value. The final charge is set by Surp and reported as `surp.charged_usd`.

The plugin does not accept wallet private keys, does not sign x402 payments, and does not automatically retry a paid request. An ambiguous timeout can leave payment state unknown, so retrying could duplicate spend.

## Cache behavior

Surp's exact-response cache stores a SHA-256 request fingerprint and completed response for 15 minutes. It applies only to deterministic, non-streaming, tool-free, single-candidate requests. An identical hit skips the upstream seller call and costs `$0.001`.

Use `surp_cache_status` before explaining a likely hit. Eligibility is not a guarantee that an entry already exists.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
hermes plugins doctor . --ci
```

No third-party runtime package is required; HTTP uses Python's standard library.

## Security

See `SECURITY.md`. The short version:

- secrets are read from the environment and never returned;
- paid calls require explicit authorization and a local ceiling;
- no raw private keys;
- no automatic paid retries;
- plugin registration performs no network access;
- public tools are read-only.

## License

MIT
