from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AgentBase(BaseModel):
    name: str
    role: str = "assistant"
    system_prompt: str = "You are a helpful AI agent."
    model: str = "grok-4.1-fast"
    tools: list[str] = Field(default_factory=list)
    channels: dict[str, Any] = Field(default_factory=dict)
    schedule: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    interaction_rules: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    is_gateway: bool = False


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    channels: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None
    skills: list[str] | None = None
    interaction_rules: dict[str, Any] | None = None
    guardrails: dict[str, Any] | None = None
    is_gateway: bool | None = None


class AgentOut(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
