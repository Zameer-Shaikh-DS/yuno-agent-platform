from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models.workflow import Workflow
from ..models.run import WorkflowRun, RunEvent, AgentMessage, TokenUsage
from ..schemas.run import WorkflowRunOut, RunEventOut, AgentMessageOut, TokenUsageOut, RunExecuteRequest
from ..runtime.executor import WorkflowExecutor
from ..models.agent import Agent
from ..services.monitor_hub import monitor_hub

router = APIRouter(prefix="/runs", tags=["runs"])


def _build_agents(db: Session, workflow: Workflow) -> dict[str, Agent]:
    agent_ids = {
        n.get("data", {}).get("agentId")
        for n in workflow.definition.get("nodes", [])
        if n.get("data", {}).get("agentId")
    }
    agents_list = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
    return {a.id: a for a in agents_list}


@router.post("/workflow/{workflow_id}/execute", response_model=WorkflowRunOut)
def execute_workflow(
    workflow_id: str,
    body: RunExecuteRequest,
    db: Session = Depends(get_db),
):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")

    run = WorkflowRun(workflow_id=workflow_id, input_text=body.input_text, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    agents = _build_agents(db, wf)

    def on_event(evt):
        monitor_hub.broadcast_threadsafe(evt)

    executor = WorkflowExecutor(db, on_event=on_event)
    try:
        executor.execute(wf, run, agents)
    except Exception as exc:
        from datetime import datetime
        run.status = "failed"
        run.output_text = f"Workflow failed: {exc}"
        run.completed_at = datetime.utcnow()
        db.commit()

    db.refresh(run)
    return run


@router.get("", response_model=list[WorkflowRunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50).all()


@router.get("/{run_id}", response_model=WorkflowRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/events", response_model=list[RunEventOut])
def get_run_events(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(RunEvent)
        .filter(RunEvent.run_id == run_id)
        .order_by(RunEvent.created_at)
        .all()
    )


@router.get("/{run_id}/messages", response_model=list[AgentMessageOut])
def get_run_messages(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(AgentMessage)
        .filter(AgentMessage.run_id == run_id)
        .order_by(AgentMessage.created_at)
        .all()
    )


@router.get("/{run_id}/tokens", response_model=list[TokenUsageOut])
def get_run_tokens(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(TokenUsage)
        .filter(TokenUsage.run_id == run_id)
        .order_by(TokenUsage.created_at)
        .all()
    )
