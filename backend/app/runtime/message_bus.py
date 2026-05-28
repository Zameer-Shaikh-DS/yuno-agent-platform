import json
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.run import AgentMessage


def publish_message(
    db: Session,
    run_id: str,
    sender_agent_id: str,
    receiver_agent_id: str,
    payload: str,
) -> AgentMessage:
    msg = AgentMessage(
        run_id=run_id,
        sender_agent_id=sender_agent_id,
        receiver_agent_id=receiver_agent_id,
        payload=payload,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_messages_for_run(db: Session, run_id: str) -> list[AgentMessage]:
    return (
        db.query(AgentMessage)
        .filter(AgentMessage.run_id == run_id)
        .order_by(AgentMessage.created_at)
        .all()
    )
