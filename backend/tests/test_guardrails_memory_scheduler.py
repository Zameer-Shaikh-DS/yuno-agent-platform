from app.models.agent import Agent
from app.services.guardrails import check_blocked_topics
from app.runtime.executor import _evaluate_condition, WorkflowExecutor
from app.models.workflow import Workflow
from app.models.run import WorkflowRun


def test_blocked_topics_enforced():
    agent = Agent(
        name="Safe",
        role="test",
        system_prompt="test",
        guardrails={"blocked_topics": ["weapon", "illegal"]},
    )
    allowed, msg = check_blocked_topics(agent, "Tell me about weapons")
    assert not allowed
    assert msg


def test_condition_contains_urgent():
    assert _evaluate_condition("contains:urgent", "This is URGENT help")
    assert not _evaluate_condition("contains:urgent", "just a question")


def test_cyclic_workflow_visits(client):
    """Feedback loop: r1 -> w1 when REVISE, max visits stops infinite loop."""
    from app.database import SessionLocal
    from app.models.agent import Agent as AgentModel

    db = SessionLocal()
    w = AgentModel(name="W", role="w", system_prompt="Write short", tools=[], guardrails={"max_iterations": 2})
    r = AgentModel(name="R", role="r", system_prompt="Say REVISE", tools=[], guardrails={"max_iterations": 2})
    db.add_all([w, r])
    db.flush()
    wf = Workflow(
        name="LoopTest",
        definition={
            "maxSteps": 10,
            "maxVisitsPerNode": 2,
            "nodes": [
                {"id": "w1", "type": "agent", "data": {"agentId": w.id}},
                {"id": "r1", "type": "agent", "data": {"agentId": r.id}},
                {"id": "e1", "type": "end", "data": {}},
            ],
            "edges": [
                {"source": "w1", "target": "r1"},
                {"source": "r1", "target": "w1", "condition": "contains:REVISE"},
                {"source": "r1", "target": "e1", "condition": "contains:APPROVED"},
            ],
        },
    )
    db.add(wf)
    db.commit()
    run = WorkflowRun(workflow_id=wf.id, input_text="draft", status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)
    out = WorkflowExecutor(db).execute(wf, run, {w.id: w, r.id: r})
    assert out
    assert run.status == "completed"
    db.close()


def test_scheduler_service_exists():
    from app.services.scheduler import agent_scheduler, scheduler_service
    assert agent_scheduler is not None
    assert hasattr(scheduler_service, "start")
    assert callable(agent_scheduler.reload_jobs)
