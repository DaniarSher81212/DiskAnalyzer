"""Конфигурация disk-analyzer: хранение API-ключей и настроек провайдеров."""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("disk-analyzer"))
CONFIG_PATH = CONFIG_DIR / "config.toml"

_DEFAULTS: dict[str, dict] = {
    "anthropic": {"model": "claude-opus-4-7"},
    "openai": {"model": "gpt-4o"},
    "ollama": {"model": "llama3.1", "url": "http://localhost:11434"},
}


def load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(_to_toml(config), encoding="utf-8")


def _to_toml(config: dict) -> str:
    lines: list[str] = []
    providers = config.get("providers", {})
    lines.append("[providers]")
    if "default" in providers:
        lines.append(f'default = "{providers["default"]}"')
    lines.append("")
    for name, settings in providers.items():
        if name == "default" or not isinstance(settings, dict):
            continue
        lines.append(f"[providers.{name}]")
        for k, v in settings.items():
            lines.append(f'{k} = "{v}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def get_provider_setting(provider: str, key: str) -> str | None:
    cfg = load()
    return cfg.get("providers", {}).get(provider, {}).get(key)


def set_provider_setting(provider: str, key: str, value: str) -> None:
    cfg = load()
    cfg.setdefault("providers", {}).setdefault(provider, {})[key] = value
    save(cfg)


def get_default_provider() -> str:
    cfg = load()
    return cfg.get("providers", {}).get("default", "anthropic")


def set_default_provider(name: str) -> None:
    cfg = load()
    cfg.setdefault("providers", {})["default"] = name
    save(cfg)


def get_api_key(provider: str) -> str | None:
    return get_provider_setting(provider, "api_key")


def get_model(provider: str) -> str | None:
    return get_provider_setting(provider, "model") or _DEFAULTS.get(provider, {}).get("model")


def get_ollama_url() -> str:
    return get_provider_setting("ollama", "url") or "http://localhost:11434"


def masked(key: str | None) -> str:
    if not key:
        return "(не задан)"
    return key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
