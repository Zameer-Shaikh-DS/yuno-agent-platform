"""Enforce agent guardrails at runtime (not UI-only)."""
from ..models.agent import Agent


def check_blocked_topics(agent: Agent, text: str) -> tuple[bool, str | None]:
    """
    Returns (allowed, refusal_message).
    blocked_topics from agent.guardrails are enforced on input and output.
    """
    topics = agent.guardrails.get("blocked_topics") if agent.guardrails else []
    if not topics:
        return True, None

    lowered = (text or "").lower()
    for topic in topics:
        t = (topic or "").strip().lower()
        if t and t in lowered:
            return False, (
                f"Request blocked by guardrails: topic '{topic}' is not allowed "
                f"for agent '{agent.name}'."
            )
    return True, None


def enforce_guardrails(agent: Agent, user_message: str, response: str) -> tuple[str, bool]:
    """
    Check input and output. Returns (final_response, was_blocked).
    """
    allowed, msg = check_blocked_topics(agent, user_message)
    if not allowed:
        return msg or "Blocked by guardrails.", True

    allowed, msg = check_blocked_topics(agent, response)
    if not allowed:
        return msg or "Response blocked by guardrails.", True

    return response, False
