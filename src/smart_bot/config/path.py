from pathlib import Path


def get_config_path() -> Path:
    return Path.home() / ".config" / "smart_bot"


def get_data_path() -> Path:
    return get_config_path() / "data"


def get_tmp_path() -> Path:
    return Path("/tmp/smart_bot")


def get_cache_path() -> Path:
    return get_config_path() / "cache"
