---
name: surp
description: "Use Surp for cheap, cache-aware LLM requests through Hermes, with Jev decision-model routing via the surp/jev preset, live market prices, trusted-seller switching and secret masking."
version: 0.4.0
author: ivcained
license: MIT
---

# Surp for Hermes

Use this skill when the user asks Hermes to choose or call a Surp route, compare Surp models or marketplace prices, inspect cache behavior, estimate cost, check Surp usage, switch between trusted and untrusted sellers, pin or block providers, or mask secrets in prompts.

## Safe workflow

1. Call `surp_models` before choosing a paid route if the user has not named one.
2. Call `surp_quote` before `surp_chat` for paid work.
3. State the route, estimated fresh price, configured ceiling, and whether exact caching is possible.
4. Call `surp_chat` only when the user has authorized the spend and set `confirm_spend: true`.
5. Read the returned `surp.cache`, `surp.routed_model`, `surp.payment_settled`, and `surp.charged_usd` fields. Never infer payment success without them. On the `surp/jev` preset, also read the `X-Surp-Jev` response header (or the `surp.jev` block) for the pick, confidence, latency, and fallback status.
6. Use `surp_jev_stats` to check Jev routing telemetry — decisions, fallback rate, shadow agreement rate, p50 decision latency — when the user asks how `surp/jev` is performing.
7. Never ask the user to paste an API key or private wallet key into chat. `SURP_API_KEY` belongs in Hermes secret configuration.

## Market prices and provider speed

- `surp_markets` (no key, free): every model's current best price, seller count and volume; pass `model` for that model's full order book with per-offer price, capacity, health and provider.
- `surp_providers` (no key, free): every provider's trusted flag plus live TPS (tokens/second, p50), TTFT, latency and uptime; pass `model` for per-model provider performance.

Use `surp_markets` whenever the user asks what models cost right now, and `surp_providers` when they ask which provider is fastest or which sellers are trusted.

## Switching sellers mid-chat

`surp_route_prefs` changes routing preferences that apply to every `surp_chat` call — no config edit, effective immediately:

- `trusted_only: true` — only providers flagged trusted in the Surplus Intelligence allowlist.
- `block_providers: [...]` — never route to these providers.
- `prefer_providers: [...]` — try these providers first, in order.
- `objective` — `price`, `latency`, or `balanced` for the router's goal.
- `mask_secrets: true` — send `X-SI-Mask-Secrets: on` so API keys, private keys and passwords in the prompt are replaced with placeholders before the request reaches the seller, then restored in the response.

`action=get` reads current prefs, `action=reset` restores defaults. For a single request, `surp_chat` accepts `providers_blocked`, `provider_order`, `si_objective` and `mask_secrets` as one-shot overrides. The response's `surp.routing_applied` shows exactly which controls were sent.

## Choosing routes

- `surp/jev`: Jev decision-model routing. TypeSafe Jev picks the route per request from a bounded candidate list, using request metadata only (never prompt content), with a confidence score and fail-open fallback to static routing. Use when the user wants the smartest available routing and accepts a small decision overhead.
- `surp/free`: sponsored chat with strict daily and per-IP limits.
- `surp/free-coding`: sponsored coding route.
- `surp/free-fast`: sponsored low-latency route.
- `surp/best-chat`: lowest-price general chat class.
- `surp/best-coding`: lowest-price coding class.
- `surp/best-reasoning`: lowest-price reasoning class.
- `surp/pro-chat`, `surp/pro-coding`, `surp/pro-reasoning`: stronger premium pools.

Use `surp_mode` only when the user asks for a routing lens:

- `cost`: cheapest eligible model.
- `value`: balance price, intelligence, and speed.
- `balanced`: even weighting.
- `speed`: favor verified output throughput.
- `intel`: favor intelligence.

## Custom combos

When the user wants a curated pool, call `surp_models` first to confirm concrete model ids, then call `surp_combo_create` with 2–20 unique ids. Creation is public and free. Surp returns a stable model id such as `surp/my/abc123`; future requests dynamically choose the cheapest available member of that pool.

Use `surp_combo_list` to discover community combos and `surp_combo_get` to inspect the complete member pool. Do not imply ownership or privacy: custom combos are public, deduplicated by their model set, and may return `existing: true` when the same set was already created.

## Exact-response cache

A request is eligible only when it is non-streaming, temperature zero, has no tools, asks for one candidate, and does not bypass the cache. Eligibility does not guarantee a hit: the full normalized request must already exist within the 15-minute TTL.

- Fresh eligible request: normal price, then the completed response may be stored.
- Identical hit: no upstream model call, $0.001.
- Changed prompt or generation setting: miss.
- Streaming, tools, non-zero temperature, `n > 1`, or explicit bypass: bypass.

Use `surp_cache_status` to explain eligibility and inspect live public counters. Treat the reported hit rate as cumulative historical evidence, not a current traffic benchmark.

## Failure handling

- Authentication error: explain that `SURP_API_KEY` is needed for paid chat or usage.
- Confirmation error: quote first and ask for explicit authorization.
- Spend-limit error: do not raise the ceiling yourself. Ask the user to change plugin settings or choose a cheaper/smaller request.
- Market unavailable: retry once for read-only discovery; do not retry paid requests automatically.
- Unknown payment state: report uncertainty and stop. Never issue a second paid request blindly.
