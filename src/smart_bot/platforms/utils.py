import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_bot.config.platform import PlatformConfig

PROVIDER_MODULE = {
    "deepseek": "smart_bot.platforms.deepseek",
    "dashscope": "smart_bot.platforms.dashscope",
    "ollama": "smart_bot.platforms.ollama",
}
PROVIDER_CLASS = {
    "deepseek": "DeepSeekLLM",
    "dashscope": "DashscopeLLM",
    "ollama": "OllamaLLM",
}


def get_provider_default_config(provider: str) -> "PlatformConfig":
    mod = importlib.import_module(PROVIDER_MODULE[provider])
    cls = getattr(mod, PROVIDER_CLASS[provider])
    return cls.default_config
