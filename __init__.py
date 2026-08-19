"""Surp Hermes plugin registration entry point."""

try:  # Hermes loads directory plugins under a generated package namespace.
    from .handlers import (
        surp_cache_status_handler,
        surp_chat_handler,
        surp_models_handler,
        surp_quote_handler,
        surp_usage_handler,
    )
    from .schemas import SURP_CACHE_STATUS, SURP_CHAT, SURP_MODELS, SURP_QUOTE, SURP_USAGE
except ImportError:  # Direct source execution and lightweight test fixtures.
    from handlers import (
        surp_cache_status_handler,
        surp_chat_handler,
        surp_models_handler,
        surp_quote_handler,
        surp_usage_handler,
    )
    from schemas import SURP_CACHE_STATUS, SURP_CHAT, SURP_MODELS, SURP_QUOTE, SURP_USAGE


_TOOLS = [
    ("surp_models", SURP_MODELS, surp_models_handler, "🔎"),
    ("surp_quote", SURP_QUOTE, surp_quote_handler, "💵"),
    ("surp_cache_status", SURP_CACHE_STATUS, surp_cache_status_handler, "♻️"),
    ("surp_chat", SURP_CHAT, surp_chat_handler, "➕"),
    ("surp_usage", SURP_USAGE, surp_usage_handler, "📊"),
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
