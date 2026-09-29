import importlib.util
from pathlib import Path


def test_plugin_registers_declared_tools():
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("surp_plugin", root / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Context:
        def __init__(self):
            self.tools = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs)

    ctx = Context()
    module.register(ctx)
    assert {x["name"] for x in ctx.tools} == {
        "surp_models",
        "surp_quote",
        "surp_cache_status",
        "surp_chat",
        "surp_usage",
        "surp_jev_stats",
        "surp_combo_create",
        "surp_combo_list",
        "surp_combo_get",
    }
    assert all(x["toolset"] == "surp" for x in ctx.tools)
    assert all(callable(x["handler"]) for x in ctx.tools)
