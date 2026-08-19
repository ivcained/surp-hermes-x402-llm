# surp-hermes-x402-llm

Standalone Hermes Agent plugin for Surp's cache-aware LLM router.

It adds five tools:

- `surp_models` — inspect live combos or models
- `surp_quote` — estimate fresh inference and the exact-cache tier without spending
- `surp_cache_status` — check cache eligibility and public cache metrics
- `surp_chat` — guarded OpenAI-compatible chat using a Surp API key
- `surp_usage` — inspect configured-key balance and usage

The bundled `surp` skill teaches Hermes how to choose routes, quote before spending, build cache-friendly requests, and interpret payment metadata.

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

The current client also accepts `SURP_BASE_URL`, `SURP_MAX_SPEND_USD`, and `SURP_TIMEOUT_SECONDS` for compatibility while standalone plugin setting access is stabilized. The API key is the only required secret.

## Payment boundary

Version 0.1 uses Surp API-key billing. It does not accept wallet private keys and does not sign x402 payments.

`surp_chat` requires both:

- `confirm_spend: true`
- a call ceiling no greater than the configured `max_spend_usd` (default `$0.05`)

The plugin does not automatically retry a paid request. An ambiguous timeout can leave payment state unknown, so retrying could duplicate spend.

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
