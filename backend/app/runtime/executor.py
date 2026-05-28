import asyncio
import logging
from datetime import datetime
from typing import Callable
from sqlalchemy.orm import Session

from ..models.agent import Agent
from ..models.workflow import Workflow
from ..models.run import WorkflowRun, RunEvent, TokenUsage
from .agent_factory import run_agent
from .message_bus import publish_message

logger = logging.getLogger("yuno.executor")


def _evaluate_condition(condition_expr: str, last_output: str) -> bool:
    expr = (condition_expr or "always").strip().lower()

    if expr in ("always", "true", ""):
        return True
    if expr in ("never", "false"):
        return False
    if expr == "escalate":
        return "urgent" in last_output.lower()
    if expr.startswith("contains:"):
        keyword = expr[len("contains:"):].strip()
        return keyword in last_output.lower()
    return expr in last_output.lower()


class WorkflowExecutor:
    def __init__(self, db: Session, on_event: Callable | None = None):
        self.db = db
        self.on_event = on_event

    def _emit(self, run_id: str, event_type: str, agent_id: str | None = None, payload: dict | None = None):
        event = RunEvent(
            run_id=run_id,
            event_type=event_type,
            agent_id=agent_id,
            payload=payload or {},
        )
        self.db.add(event)
        self.db.commit()
        if self.on_event:
            self.on_event(
                {
                    "run_id": run_id,
                    "event_type": event_type,
                    "agent_id": agent_id,
                    "payload": payload or {},
                    "created_at": event.created_at.isoformat(),
                }
            )

    def _record_tokens(self, run_id: str, agent_id: str, usage: dict):
        tu = TokenUsage(
            run_id=run_id,
            agent_id=agent_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            estimated_cost_usd=usage.get("estimated_cost_usd", 0.0),
        )
        self.db.add(tu)
        self.db.commit()
        if self.on_event:
            self.on_event(
                {
                    "run_id": run_id,
                    "event_type": "token_usage",
                    "agent_id": agent_id,
                    "payload": {
                        "input_tokens": tu.input_tokens,
                        "output_tokens": tu.output_tokens,
                        "total_tokens": tu.total_tokens,
                        "estimated_cost_usd": tu.estimated_cost_usd,
                    },
                }
            )

    def execute(self, workflow: Workflow, run: WorkflowRun, agents: dict[str, Agent]) -> str:
        definition = workflow.definition
        nodes = {n["id"]: n for n in definition.get("nodes", [])}
        edges = definition.get("edges", [])
        input_text = run.input_text

        run.status = "running"
        self.db.commit()
        self._emit(run.id, "run_started", payload={"workflow_id": workflow.id})

        blocked_nodes: set[str] = set()
        node_order = self._topological_order(nodes, edges)
        context = ""
        last_output = input_text

        for node_id in node_order:
            if node_id in blocked_nodes:
                self._emit(run.id, "step_skipped", payload={"node_id": node_id, "reason": "condition blocked"})
                for edge in edges:
                    if edge.get("source") == node_id:
                        blocked_nodes.add(edge["target"])
                continue

            node = nodes.get(node_id)
            if not node:
                continue

            ntype = node.get("type", "agent")

            if ntype == "end":
                break

            if ntype == "condition":
                condition_expr = node.get("data", {}).get("condition", "always")
                condition_text = f"{input_text}\n{last_output}"
                passes = _evaluate_condition(condition_expr, condition_text)
                self._emit(
                    run.id,
                    "condition_evaluated",
                    payload={
                        "node_id": node_id,
                        "condition": condition_expr,
                        "passes": passes,
                        "output_snippet": last_output[:200],
                    },
                )
                if not passes:
                    for edge in edges:
                        if edge.get("source") == node_id:
                            blocked_nodes.add(edge["target"])
                continue

            if ntype != "agent":
                continue

            agent_id = node.get("data", {}).get("agentId")
            agent = agents.get(agent_id)
            if not agent:
                self._emit(run.id, "step_skipped", payload={"node_id": node_id, "reason": "agent not found"})
                continue

            self._emit(run.id, "agent_started", agent_id=agent.id, payload={"node_id": node_id})

            prompt = node.get("data", {}).get("prompt") or last_output
            if context:
                prompt = f"{prompt}\n\nPrior context:\n{context}"

            result = run_agent(agent, prompt, context=context)
            last_output = result["response"]
            self._record_tokens(run.id, agent.id, result)

            self._emit(
                run.id,
                "agent_completed",
                agent_id=agent.id,
                payload={"output_preview": last_output[:500]},
            )

            next_agents = self._next_agent_nodes(node_id, edges, nodes, blocked_nodes)
            for next_node in next_agents:
                next_agent_id = next_node.get("data", {}).get("agentId")
                if next_agent_id and next_agent_id in agents:
                    publish_message(self.db, run.id, agent.id, next_agent_id, last_output)
                    self._emit(
                        run.id,
                        "agent_message",
                        agent_id=agent.id,
                        payload={"to": next_agent_id, "preview": last_output[:300]},
                    )

            context = f"{context}\n\n[{agent.name}]: {last_output}".strip()

        run.status = "completed"
        run.output_text = last_output
        run.completed_at = datetime.utcnow()
        self.db.commit()
        self._emit(run.id, "run_completed", payload={"output_preview": last_output[:500]})
        return last_output

    def _topological_order(self, nodes: dict, edges: list) -> list[str]:
        incoming = {nid: 0 for nid in nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in nodes}
        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            if src in adj and tgt in incoming:
                adj[src].append(tgt)
                incoming[tgt] = incoming.get(tgt, 0) + 1
        queue = [nid for nid, deg in incoming.items() if deg == 0]
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in adj.get(n, []):
                incoming[m] -= 1
                if incoming[m] == 0:
                    queue.append(m)
        for nid in nodes:
            if nid not in order:
                order.append(nid)
        return order

    def _next_agent_nodes(self, node_id: str, edges: list, nodes: dict, blocked: set[str]) -> list[dict]:
        result = []
        for e in edges:
            if e.get("source") == node_id:
                tgt_id = e.get("target")
                if tgt_id in blocked:
                    continue
                tgt = nodes.get(tgt_id)
                if tgt and tgt.get("type") == "agent":
                    result.append(tgt)
        return result


async def execute_workflow_async(db: Session, workflow_id: str, input_text: str, on_event=None) -> WorkflowRun:
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise ValueError("Workflow not found")

    run = WorkflowRun(workflow_id=workflow_id, input_text=input_text, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    agent_ids = {
        n.get("data", {}).get("agentId")
        for n in workflow.definition.get("nodes", [])
        if n.get("data", {}).get("agentId")
    }
    agents_list = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
    agents = {a.id: a for a in agents_list}

    executor = WorkflowExecutor(db, on_event=on_event)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, executor.execute, workflow, run, agents)
    db.refresh(run)
    return run
