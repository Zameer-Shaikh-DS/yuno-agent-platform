from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class RunExecuteRequest(BaseModel):
    input_text: str = ""


class WorkflowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    status: str
    input_text: str
    output_text: str
    created_at: datetime
    completed_at: datetime | None = None


class RunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    event_type: str
    agent_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class AgentMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    sender_agent_id: str
    receiver_agent_id: str
    payload: str
    created_at: datetime


class TokenUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    agent_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    created_at: datetime
