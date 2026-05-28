from sqlalchemy.orm import Session
from .config import get_settings
from .llm_provider import resolve_llm_config
from .models.agent import Agent
from .models.workflow import Workflow

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def migrate_agent_models(db: Session) -> None:
    """Fix DB agents still using old grok-* model ids when using Groq."""
    settings = get_settings()
    cfg = resolve_llm_config(
        api_key=settings.llm_api_key,
        mock_llm=settings.mock_llm,
        provider_override=settings.llm_provider,
    )
    target = cfg.default_model if cfg.provider != "mock" else DEFAULT_MODEL
    changed = False
    for agent in db.query(Agent).all():
        if not agent.model or agent.model.startswith("grok"):
            agent.model = target
            changed = True
    if changed:
        db.commit()


def seed_database(db: Session):
    migrate_agent_models(db)
    if db.query(Agent).count() > 0:
        return

    researcher = Agent(
        name="Researcher",
        role="research",
        system_prompt="You are a research agent. Summarize facts clearly. Be concise.",
        model=DEFAULT_MODEL,
        tools=["web_search", "note_store"],
        skills=["research", "analysis"],
        memory={"window": 10, "summary": ""},
        schedule={"cron": "0 9 * * *", "timezone": "UTC", "enabled": False},
        interaction_rules={"handoff_format": "bullet_points"},
        guardrails={"max_iterations": 6, "blocked_topics": []},
        channels={"telegram": {"enabled": False}},
        is_gateway=False,
    )
    writer = Agent(
        name="Writer",
        role="content",
        system_prompt="You are a writer agent. Turn research into clear summaries.",
        model=DEFAULT_MODEL,
        tools=["note_store"],
        skills=["writing"],
        memory={"window": 10},
        guardrails={"max_iterations": 5},
        channels={"telegram": {"enabled": False}},
    )
    triage = Agent(
        name="SupportTriage",
        role="support",
        system_prompt="Classify user issues as 'urgent' or 'normal'. Reply with classification only.",
        model=DEFAULT_MODEL,
        tools=["calculator"],
        skills=["classification"],
        guardrails={"max_iterations": 4},
    )
    support = Agent(
        name="SupportResponder",
        role="support",
        system_prompt="You resolve customer support issues professionally and briefly.",
        model=DEFAULT_MODEL,
        tools=["note_store"],
        skills=["support"],
        guardrails={"max_iterations": 5},
    )
    gateway = Agent(
        name="TelegramGateway",
        role="gateway",
        system_prompt="You are the user-facing assistant. Answer helpfully using tools when needed.",
        model=DEFAULT_MODEL,
        tools=["web_search", "calculator", "note_store"],
        channels={"telegram": {"enabled": True}},
        is_gateway=True,
    )

    db.add_all([researcher, writer, triage, support, gateway])
    db.flush()

    research_writer = Workflow(
        name="Research → Writer",
        description="Agent A researches, then asynchronously hands off to Writer for summary.",
        is_template=True,
        definition={
            "nodes": [
                {"id": "n1", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"agentId": researcher.id, "label": "Researcher"}},
                {"id": "n2", "type": "agent", "position": {"x": 300, "y": 0}, "data": {"agentId": writer.id, "label": "Writer"}},
                {"id": "n3", "type": "end", "position": {"x": 600, "y": 0}, "data": {"label": "End"}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2", "label": "success"},
                {"id": "e2", "source": "n2", "target": "n3", "label": "success"},
            ],
        },
    )
    support_triage = Workflow(
        name="Support Triage",
        description="Triage classifies issue, condition routes to responder or loop.",
        is_template=True,
        definition={
            "nodes": [
                {"id": "t1", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"agentId": triage.id, "label": "Triage"}},
                {"id": "c1", "type": "condition", "position": {"x": 200, "y": 100}, "data": {"condition": "contains:urgent", "label": "Urgent?"}},
                {"id": "t2", "type": "agent", "position": {"x": 400, "y": 0}, "data": {"agentId": support.id, "label": "Responder"}},
                {"id": "t3", "type": "end", "position": {"x": 600, "y": 0}, "data": {"label": "End"}},
            ],
            "edges": [
                {"id": "e1", "source": "t1", "target": "c1"},
                {"id": "e2", "source": "c1", "target": "t2", "label": "urgent"},
                {"id": "e3", "source": "t2", "target": "t3"},
            ],
        },
    )
    db.add_all([research_writer, support_triage])
    db.commit()
