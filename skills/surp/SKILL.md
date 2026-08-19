---
name: surp
description: "Use Surp for cheap, cache-aware LLM requests through Hermes."
version: 0.1.0
author: ivcained
license: MIT
---

# Surp for Hermes

Use this skill when the user asks Hermes to choose or call a Surp route, compare Surp models, inspect cache behavior, estimate cost, or check Surp usage.

## Safe workflow

1. Call `surp_models` before choosing a paid route if the user has not named one.
2. Call `surp_quote` before `surp_chat` for paid work.
3. State the route, estimated fresh price, configured ceiling, and whether exact caching is possible.
4. Call `surp_chat` only when the user has authorized the spend and set `confirm_spend: true`.
5. Read the returned `surp.cache`, `surp.routed_model`, `surp.payment_settled`, and `surp.charged_usd` fields. Never infer payment success without them.
6. Never ask the user to paste an API key or private wallet key into chat. `SURP_API_KEY` belongs in Hermes secret configuration.

## Choosing routes

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
