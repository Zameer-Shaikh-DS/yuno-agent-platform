import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..llm_provider import resolve_llm_config, resolve_model_for_agent
from ..models.agent import Agent
from ..services.guardrails import check_blocked_topics, enforce_guardrails
from ..services.memory_store import (
    append_memory_turn,
    format_memory_for_prompt,
    get_memory_window,
    trim_memory,
)
from ..tools.registry import get_tools_for_agent, web_search

logger = logging.getLogger("yuno.agent_factory")

# Rough pricing estimate per 1M tokens (USD) for cost display
MODEL_COSTS = {
    "grok-3-mini": (0.20, 0.50),
    "grok-3": (3.0, 15.0),
    "llama-3.3-70b-versatile": (0.10, 0.30),
    "default": (1.0, 3.0),
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _is_blocked_by_topic(agent: Agent, user_message: str, context: str) -> str | None:
    blocked = (agent.guardrails or {}).get("blocked_topics") or []
    if not blocked:
        return None
    haystack = f"{user_message}\n{context}".lower()
    for topic in blocked:
        topic_text = _normalize_text(str(topic))
        if topic_text and topic_text in haystack:
            return topic_text
    return None


def _memory_window_excerpt(context: str, memory_cfg: dict) -> str:
    if not context:
        return ""
    try:
        window = int((memory_cfg or {}).get("window", 0))
    except Exception:
        window = 0
    if window <= 0:
        return ""
    # Context is appended as "[Agent]: message" chunks; preserve most recent N chunks.
    chunks = [c.strip() for c in context.split("\n\n") if c.strip()]
    if not chunks:
        return ""
    recent = chunks[-window:]
    return "\n\n".join(recent)


def _build_llm(agent: Agent) -> ChatOpenAI:
    settings = get_settings()
    llm_cfg = resolve_llm_config(
        api_key=settings.llm_api_key,
        model=settings.groq_model if settings.llm_provider == "groq" else settings.xai_model,
        mock_llm=settings.mock_llm,
        provider_override=settings.llm_provider,
    )
    if llm_cfg.provider == "mock":
        return ChatOpenAI(
            model="mock",
            api_key="mock",
            base_url=llm_cfg.base_url,
            temperature=0,
        )
    model = resolve_model_for_agent(agent.model, llm_cfg)
    if not llm_cfg.api_key:
        raise ValueError(
            "No LLM API key. Set XAI_API_KEY (xai-...) for Grok or GROQ_API_KEY / gsk_ key for Groq free tier."
        )
    return ChatOpenAI(
        model=model,
        api_key=llm_cfg.api_key,
        base_url=llm_cfg.base_url,
        temperature=0.2,
    )


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp_rate, out_rate = MODEL_COSTS.get(model, MODEL_COSTS["default"])
    return (input_tokens * inp_rate + output_tokens * out_rate) / 1_000_000


def _prepare_groq_message_and_tools(
    agent: Agent,
    user_message: str,
    tools: list,
    llm_cfg,
) -> tuple[str, list]:
    """Groq sometimes fails tool_use for web_search — run search inline instead."""
    tool_names = agent.tools or []
    if llm_cfg.provider != "groq" or "web_search" not in tool_names:
        return user_message, tools

    try:
        search_text = web_search.invoke({"query": user_message[:300]})
        enriched = (
            f"{user_message}\n\n"
            f"[Pre-fetched web search — use this in your answer]\n{search_text}"
        )
        filtered = [t for t in tools if getattr(t, "name", "") != "web_search"]
        return enriched, filtered
    except Exception as exc:
        logger.warning("Inline web_search failed: %s", exc)
        return user_message, [t for t in tools if getattr(t, "name", "") != "web_search"]


def _invoke_graph(llm, tools: list, full_prompt: str, user_message: str, max_iter: int) -> dict:
    graph = create_react_agent(llm, tools, prompt=full_prompt)
    return graph.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config={"recursion_limit": max_iter},
    )


def run_agent(
    agent: Agent,
    user_message: str,
    context: str = "",
    db: Session | None = None,
) -> dict[str, Any]:
    """Run a single agent with LangGraph ReAct. Returns response + token usage."""
    settings = get_settings()
    own_db = db is None
    if own_db:
        db = SessionLocal()

    try:
        allowed, refusal = check_blocked_topics(agent, user_message)
        if not allowed:
            return {
                "response": refusal or "Blocked by guardrails.",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "guardrail_blocked": True,
            }

        return _run_agent_inner(agent, user_message, context, settings, db)
    finally:
        if own_db and db:
            db.close()


def _run_agent_inner(
    agent: Agent,
    user_message: str,
    context: str,
    settings,
    db: Session,
) -> dict[str, Any]:
    if settings.mock_llm:
        blocked_topic = _is_blocked_by_topic(agent, user_message, context)
        if blocked_topic:
            return {
                "response": f"[MOCK {agent.name}] Request blocked due to guardrail topic: {blocked_topic}",
                "input_tokens": 5,
                "output_tokens": 8,
                "total_tokens": 13,
                "estimated_cost_usd": 0.0,
            }
        return {
            "response": f"[MOCK {agent.name}] Processed: {user_message[:200]}",
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "estimated_cost_usd": 0.0,
        }

    llm_cfg = resolve_llm_config(
        api_key=settings.llm_api_key,
        mock_llm=settings.mock_llm,
        provider_override=settings.llm_provider,
    )
    llm = _build_llm(agent)
    tools = get_tools_for_agent(agent.tools or [])
    user_message, tools = _prepare_groq_message_and_tools(agent, user_message, tools, llm_cfg)

    memory_cfg = agent.memory or {}
    try:
        window = int(memory_cfg.get("window", 10) or 10)
    except Exception:
        window = 10

    prompt_parts = [agent.system_prompt]
    if memory_cfg.get("summary"):
        prompt_parts.append(f"Memory summary: {memory_cfg['summary']}")
    if db and window > 0:
        turns = get_memory_window(db, agent.id, window)
        mem_text = format_memory_for_prompt(turns)
        if mem_text:
            prompt_parts.append(mem_text)
    recent_memory = _memory_window_excerpt(context, memory_cfg)
    if recent_memory:
        prompt_parts.append(f"Workflow context window:\n{recent_memory}")
    if context:
        prompt_parts.append(f"Context from other agents:\n{context}")
    if llm_cfg.provider == "groq" and tools:
        prompt_parts.append(
            "Use tools only when necessary. Prefer a direct answer when context is already provided."
        )
    full_prompt = "\n\n".join(prompt_parts)

    max_iter = agent.guardrails.get("max_iterations", 8)
    try:
        result = _invoke_graph(llm, tools, full_prompt, user_message, max_iter)
    except Exception as exc:
        err = str(exc)
        if "tool_use_failed" in err or "Failed to call a function" in err:
            logger.warning("Tool call failed for %s, retrying without tools: %s", agent.name, err)
            fallback_prompt = full_prompt + "\n\nTools are unavailable. Answer directly and concisely."
            result = _invoke_graph(llm, [], fallback_prompt, user_message, max_iter)
        else:
            raise

    final_messages = result.get("messages", [])
    response_text = ""
    if final_messages:
        last = final_messages[-1]
        response_text = getattr(last, "content", str(last))

    response_text, blocked = enforce_guardrails(agent, user_message, str(response_text))
    if blocked and db:
        append_memory_turn(db, agent.id, "user", user_message[:2000])
        append_memory_turn(db, agent.id, "assistant", response_text[:2000])
        return {
            "response": response_text,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "guardrail_blocked": True,
        }

    if db and window > 0 and not blocked:
        append_memory_turn(db, agent.id, "user", user_message[:2000])
        append_memory_turn(db, agent.id, "assistant", str(response_text)[:2000])
        trim_memory(db, agent.id, keep=max(window * 2, 20))

    input_tokens = output_tokens = 0
    for msg in final_messages:
        usage = getattr(msg, "usage_metadata", None) or getattr(msg, "response_metadata", {}).get("token_usage")
        if usage:
            if isinstance(usage, dict):
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
            else:
                input_tokens += getattr(usage, "input_tokens", 0)
                output_tokens += getattr(usage, "output_tokens", 0)

    if input_tokens == 0:
        input_tokens = len(user_message.split()) * 2
        output_tokens = len(str(response_text).split()) * 2

    total = input_tokens + output_tokens
    llm_cfg = resolve_llm_config(
        api_key=settings.llm_api_key,
        mock_llm=settings.mock_llm,
        provider_override=settings.llm_provider,
    )
    model_name = resolve_model_for_agent(agent.model, llm_cfg)
    cost = _estimate_cost(model_name, input_tokens, output_tokens)

    return {
        "response": response_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "estimated_cost_usd": cost,
    }
