"""Surp Hermes plugin registration entry point."""

try:
    from .handlers import (
        surp_cache_status_handler, surp_chat_handler, surp_models_handler,
        surp_quote_handler, surp_usage_handler, surp_combo_create_handler,
        surp_combo_list_handler, surp_combo_get_handler, surp_jev_stats_handler,
    )
    from .schemas import (
        SURP_CACHE_STATUS, SURP_CHAT, SURP_MODELS, SURP_QUOTE, SURP_USAGE,
        SURP_COMBO_CREATE, SURP_COMBO_LIST, SURP_COMBO_GET, SURP_JEV_STATS,
    )
except ImportError:
    from handlers import (
        surp_cache_status_handler, surp_chat_handler, surp_models_handler,
        surp_quote_handler, surp_usage_handler, surp_combo_create_handler,
        surp_combo_list_handler, surp_combo_get_handler, surp_jev_stats_handler,
    )
    from schemas import (
        SURP_CACHE_STATUS, SURP_CHAT, SURP_MODELS, SURP_QUOTE, SURP_USAGE,
        SURP_COMBO_CREATE, SURP_COMBO_LIST, SURP_COMBO_GET, SURP_JEV_STATS,
    )


_TOOLS = [
    ("surp_models", SURP_MODELS, surp_models_handler, "🔎"),
    ("surp_quote", SURP_QUOTE, surp_quote_handler, "💵"),
    ("surp_cache_status", SURP_CACHE_STATUS, surp_cache_status_handler, "♻️"),
    ("surp_chat", SURP_CHAT, surp_chat_handler, "➕"),
    ("surp_usage", SURP_USAGE, surp_usage_handler, "📊"),
    ("surp_jev_stats", SURP_JEV_STATS, surp_jev_stats_handler, "🧠"),
    ("surp_combo_create", SURP_COMBO_CREATE, surp_combo_create_handler, "🧩"),
    ("surp_combo_list", SURP_COMBO_LIST, surp_combo_list_handler, "📚"),
    ("surp_combo_get", SURP_COMBO_GET, surp_combo_get_handler, "🔬"),
]


def register(ctx) -> None:
    """Register Surp tools. Called once by Hermes' plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="surp",
            schema=schema,
            handler=handler,
            description=schema["function"]["description"],
            emoji=emoji,
        )
