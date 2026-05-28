"""Resolve LLM API client settings (xAI Grok vs Groq — keys are not interchangeable)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # "xai" | "groq" | "mock"
    api_key: str
    base_url: str
    default_model: str


# Legacy UI / seed names → current API model ids
XAI_MODEL_ALIASES = {
    "grok-4.1-fast": "grok-3-mini",
    "grok-4.3": "grok-3",
    "grok-4": "grok-3",
}

GROQ_MODEL_ALIASES = {
    "grok-4.1-fast": "llama-3.3-70b-versatile",
    "grok-4.3": "llama-3.3-70b-versatile",
    "grok-3-mini": "llama-3.3-70b-versatile",
    "grok-3": "llama-3.3-70b-versatile",
}


def resolve_llm_config(
    *,
    api_key: str = "",
    model: str = "",
    mock_llm: bool = False,
    provider_override: str = "",
) -> LLMConfig:
    if mock_llm:
        return LLMConfig("mock", "mock", "https://api.x.ai/v1", "mock")

    key = (
        api_key
        or os.getenv("LLM_API_KEY", "")
        or os.getenv("GROQ_API_KEY", "")
        or os.getenv("XAI_API_KEY", "")
    ).strip()

    provider = (provider_override or os.getenv("LLM_PROVIDER", "")).strip().lower()

    if not provider:
        if key.startswith("gsk_"):
            provider = "groq"
        elif key.startswith("xai-"):
            provider = "xai"
        elif os.getenv("GROQ_API_KEY"):
            provider = "groq"
        else:
            provider = "xai"

    if provider == "groq":
        base = "https://api.groq.com/openai/v1"
        default = model or os.getenv("GROQ_MODEL") or os.getenv("XAI_MODEL") or "llama-3.3-70b-versatile"
        default = GROQ_MODEL_ALIASES.get(default, default)
        return LLMConfig("groq", key, base, default)

    base = "https://api.x.ai/v1"
    default = model or os.getenv("XAI_MODEL") or "grok-3-mini"
    default = XAI_MODEL_ALIASES.get(default, default)
    return LLMConfig("xai", key, base, default)


def resolve_model_for_agent(agent_model: str | None, llm: LLMConfig) -> str:
    raw = (agent_model or llm.default_model).strip()
    if llm.provider == "groq":
        return GROQ_MODEL_ALIASES.get(raw, raw)
    if llm.provider == "xai":
        return XAI_MODEL_ALIASES.get(raw, raw)
    return raw
