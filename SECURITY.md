# Security policy

## Supported versions

Security fixes are applied to the latest release.

## Report a vulnerability

Do not open a public issue for API-key exposure, payment bypass, request replay, or spend-limit bypass. Contact the repository owner privately through GitHub.

Include the affected version, reproduction steps, and whether money or credentials were exposed. Remove real keys, signatures, wallet seeds, and private prompts from reports.

## Trust boundaries

The plugin runs inside Hermes with the user's permissions. It is not a sandbox.

- Surp and the selected upstream seller receive inference requests.
- `SURP_API_KEY` is read from the process environment.
- Tool output must never include credentials.
- A quote is informational; only `surp_chat` can create a paid request.
- `confirm_spend` is an explicit model-visible authorization flag, not a substitute for Hermes' own approval controls.
- The configured per-request ceiling is enforced before network I/O.
- Paid calls are never automatically retried because payment state may be ambiguous after a timeout.
- This release does not handle private keys or sign x402 payloads.

## Operator recommendations

- Create a dedicated Surp key with a low budget.
- Keep the default `$0.05` per-request ceiling until usage is understood.
- Revoke a key immediately if tool output or logs expose it.
- Review upstream-provider retention policies for sensitive prompts.
