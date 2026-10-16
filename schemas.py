"""JSON schemas exposed to Hermes' model tool registry."""


def schema(name, description, properties, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


SURP_MODELS = schema(
    "surp_models",
    "List live Surp routing combos or underlying models with current prices. Read-only and free; use before choosing a route.",
    {
        "kind": {"type": "string", "enum": ["combos", "models"], "default": "combos"},
        "model_class": {"type": "string", "enum": ["chat", "coding", "reasoning", "fast", "vision"]},
        "pro": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
    },
)

SURP_QUOTE = schema(
    "surp_quote",
    "Estimate a fresh Surp request and show the exact-cache-hit price without spending money. A quote is not a payment authorization.",
    {
        "model": {"type": "string", "description": "Surp combo, for example surp/best-chat"},
        "max_tokens": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1500},
        "cacheable": {"type": "boolean", "description": "Whether the intended request follows exact-cache eligibility rules."},
    },
    ("model",),
)

SURP_CACHE_STATUS = schema(
    "surp_cache_status",
    "Inspect public Surp cache metrics or explain whether request settings are eligible for the 15-minute exact-response cache. Read-only and free.",
    {
        "request": {"type": "object", "description": "Optional OpenAI chat request settings to check for eligibility."},
    },
)

SURP_CHAT = schema(
    "surp_chat",
    "Make a paid Surp OpenAI-compatible chat request using SURP_API_KEY. Requires confirm_spend=true. Refuses the request before sending it if Surp's live price for max_tokens (default 1500) exceeds max_spend_usd or the configured per-request ceiling. Returns routing, settlement, and cache metadata.",
    {
        "model": {"type": "string"},
        "messages": {"type": "array", "items": {"type": "object"}, "minItems": 1},
        "confirm_spend": {"type": "boolean", "description": "Must be true after the user has authorized spending."},
        "max_spend_usd": {"type": "number", "minimum": 0, "maximum": 1},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2, "default": 0},
        "max_tokens": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1500},
        "stream": {"type": "boolean", "default": False},
        "surp_bypass_cache": {"type": "boolean", "default": False},
        "surp_mode": {"type": "string", "enum": ["cost", "value", "balanced", "speed", "intel"]},
    },
    ("model", "messages", "confirm_spend"),
)

SURP_USAGE = schema(
    "surp_usage",
    "Read balance and usage for the configured SURP_API_KEY. Read-only; never returns the key itself.",
    {},
)

SURP_JEV_STATS = schema(
    "surp_jev_stats",
    "Show Jev decision-model routing telemetry from the Surp gateway: total routing decisions, fallback rate, shadow agreement rate, p50 decision latency, and whether shadow and live Jev routing are enabled. Use this to check how the surp/jev preset is performing or whether Jev routing is active. No API key required.",
    {},
)

SURP_COMBO_CREATE = schema(
    "surp_combo_create",
    "Create or reuse a public custom Surp combo from 2 to 20 concrete model ids. It dynamically routes to the cheapest available member. Creating it does not spend money.",
    {
        "name": {"type": "string", "maxLength": 80},
        "models": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 20, "uniqueItems": True},
    },
    ("models",),
)

SURP_COMBO_LIST = schema(
    "surp_combo_list",
    "List public community-created Surp combos and their current cheapest routes. Free and read-only.",
    {},
)

SURP_COMBO_GET = schema(
    "surp_combo_get",
    "Inspect one public custom Surp combo, including its member pool and current routed model. Free and read-only.",
    {"slug": {"type": "string"}},
    ("slug",),
)
