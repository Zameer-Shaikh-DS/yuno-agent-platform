from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.agent import Agent
from ..models.schedule_log import ScheduledRunLog
from ..services.scheduler import agent_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/jobs")
def list_scheduled_jobs():
    return {"jobs": agent_scheduler.list_jobs()}


@router.post("/reload")
def reload_scheduler():
    agent_scheduler.reload_jobs()
    return {"status": "reloaded", "jobs": agent_scheduler.list_jobs()}


@router.get("/logs")
def list_schedule_logs(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(ScheduledRunLog)
        .order_by(ScheduledRunLog.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "status": r.status,
            "input_text": r.input_text,
            "output_text": r.output_text[:500],
            "error": r.error,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/agents/{agent_id}/schedule")
def get_agent_schedule(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return {"error": "not found"}
    return {"agent_id": agent.id, "name": agent.name, "schedule": agent.schedule or {}}
