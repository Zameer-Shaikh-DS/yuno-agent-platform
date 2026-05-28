from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    definition: dict[str, Any]
    is_template: bool = False


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict[str, Any] | None = None
    is_template: bool | None = None


class WorkflowOut(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
