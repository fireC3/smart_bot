from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .capability import ModelCapability


class PlatformConfig(BaseModel):
    """Platform configuration model.

    Single source of truth for platform/provider settings — used both for
    JSON persistence and as the runtime config passed to LLM providers.
    """
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout: int = 60
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int | None = None
    models: list[str] = Field(default_factory=list)
    capability: ModelCapability = Field(default_factory=ModelCapability)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_platform_dict(cls, platform_id: str, data: dict[str, Any]) -> PlatformConfig:
        capability_data = data.get("capability")
        capability = ModelCapability.from_dict(capability_data) if capability_data else ModelCapability()
        return cls(
            provider=data.get("provider", ""),
            base_url=data.get("base_url", ""),
            api_key=data.get("api_key", ""),
            timeout=data.get("timeout", 60),
            max_retries=data.get("max_retries", 3),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            models=data.get("models", []),
            capability=capability,
            extra_parameters=data.get("extra_parameters", {}),
        )
