"""Agent memory window: persist and inject last N turns (not summary-only)."""
from sqlalchemy.orm import Session

from ..models.memory import AgentMemoryTurn


def get_memory_window(db: Session, agent_id: str, window: int) -> list[dict[str, str]]:
    if window <= 0:
        return []
    rows = (
        db.query(AgentMemoryTurn)
        .filter(AgentMemoryTurn.agent_id == agent_id)
        .order_by(AgentMemoryTurn.created_at.desc())
        .limit(window)
        .all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


def format_memory_for_prompt(turns: list[dict[str, str]]) -> str:
    if not turns:
        return ""
    lines = []
    for t in turns:
        role = t["role"].capitalize()
        lines.append(f"{role}: {t['content']}")
    return "Recent conversation memory:\n" + "\n".join(lines)


def append_memory_turn(db: Session, agent_id: str, role: str, content: str) -> None:
    db.add(AgentMemoryTurn(agent_id=agent_id, role=role, content=content[:8000]))
    db.commit()


def trim_memory(db: Session, agent_id: str, keep: int = 50) -> None:
    """Keep only the latest `keep` turns per agent."""
    if keep <= 0:
        return
    ids = (
        db.query(AgentMemoryTurn.id)
        .filter(AgentMemoryTurn.agent_id == agent_id)
        .order_by(AgentMemoryTurn.created_at.desc())
        .offset(keep)
        .all()
    )
    if ids:
        db.query(AgentMemoryTurn).filter(AgentMemoryTurn.id.in_([i[0] for i in ids])).delete(
            synchronize_session=False
        )
        db.commit()
