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
        definition = workflow.definition or {}
        nodes = {n["id"]: n for n in definition.get("nodes", []) if n.get("id")}
        edges = definition.get("edges", [])
        input_text = run.input_text

        run.status = "running"
        self.db.commit()
        self._emit(run.id, "run_started", payload={"workflow_id": workflow.id})

        context = ""
        last_output = input_text

        outgoing: dict[str, list[tuple[str, str]]] = {}
        incoming_count: dict[str, int] = {nid: 0 for nid in nodes}
        for e in edges:
            src = e.get("source")
            tgt = e.get("target")
            if src in nodes and tgt in nodes:
                edge_condition = str(e.get("condition") or "").strip()
                outgoing.setdefault(src, []).append((tgt, edge_condition))
                incoming_count[tgt] = incoming_count.get(tgt, 0) + 1

        queue: list[str] = [nid for nid, deg in incoming_count.items() if deg == 0]
        if not queue and nodes:
            queue = [next(iter(nodes.keys()))]

        max_steps = int(definition.get("maxSteps") or max(20, len(nodes) * 6))
        max_visits_per_node = int(definition.get("maxVisitsPerNode") or 5)
        visit_count: dict[str, int] = {}
        steps = 0

        while queue and steps < max_steps:
            node_id = queue.pop(0)
            steps += 1
            visit_count[node_id] = visit_count.get(node_id, 0) + 1
            if visit_count[node_id] > max_visits_per_node:
                self._emit(
                    run.id,
                    "step_skipped",
                    payload={"node_id": node_id, "reason": "max node visits reached", "max": max_visits_per_node},
                )
                continue

            node = nodes.get(node_id)
            if not node:
                continue

            ntype = node.get("type", "agent")
            if ntype == "end":
                self._emit(run.id, "run_path_end", payload={"node_id": node_id})
                continue

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
                if passes:
                    for target, edge_cond in outgoing.get(node_id, []):
                        if edge_cond and not _evaluate_condition(edge_cond, condition_text):
                            self._emit(
                                run.id,
                                "step_skipped",
                                payload={"node_id": target, "reason": f"edge condition blocked: {edge_cond}"},
                            )
                            continue
                        queue.append(target)
                else:
                    for target, _ in outgoing.get(node_id, []):
                        self._emit(
                            run.id,
                            "step_skipped",
                            payload={"node_id": target, "reason": "condition blocked"},
                        )
                continue

            if ntype != "agent":
                for target, edge_cond in outgoing.get(node_id, []):
                    edge_text = f"{input_text}\n{last_output}"
                    if edge_cond and not _evaluate_condition(edge_cond, edge_text):
                        self._emit(
                            run.id,
                            "step_skipped",
                            payload={"node_id": target, "reason": f"edge condition blocked: {edge_cond}"},
                        )
                        continue
                    queue.append(target)
                continue

            agent_id = node.get("data", {}).get("agentId")
            agent = agents.get(agent_id)
            if not agent:
                self._emit(run.id, "step_skipped", payload={"node_id": node_id, "reason": "agent not found"})
                for target, edge_cond in outgoing.get(node_id, []):
                    edge_text = f"{input_text}\n{last_output}"
                    if edge_cond and not _evaluate_condition(edge_cond, edge_text):
                        self._emit(
                            run.id,
                            "step_skipped",
                            payload={"node_id": target, "reason": f"edge condition blocked: {edge_cond}"},
                        )
                        continue
                    queue.append(target)
                continue

            self._emit(run.id, "agent_started", agent_id=agent.id, payload={"node_id": node_id})

            prompt = node.get("data", {}).get("prompt") or last_output
            if context:
                prompt = f"{prompt}\n\nPrior context:\n{context}"

            result = run_agent(agent, prompt, context=context, db=self.db)
            last_output = result["response"]
            self._record_tokens(run.id, agent.id, result)

            self._emit(
                run.id,
                "agent_completed",
                agent_id=agent.id,
                payload={"output_preview": last_output[:500]},
            )

            next_targets = []
            edge_text = f"{input_text}\n{last_output}"
            for target_id, edge_cond in outgoing.get(node_id, []):
                if edge_cond and not _evaluate_condition(edge_cond, edge_text):
                    self._emit(
                        run.id,
                        "step_skipped",
                        payload={"node_id": target_id, "reason": f"edge condition blocked: {edge_cond}"},
                    )
                    continue
                next_targets.append(target_id)

            for target_id in next_targets:
                next_node = nodes.get(target_id)
                if not next_node:
                    continue
                if next_node.get("type") == "agent":
                    next_agent_id = next_node.get("data", {}).get("agentId")
                    if next_agent_id and next_agent_id in agents:
                        publish_message(self.db, run.id, agent.id, next_agent_id, last_output)
                        self._emit(
                            run.id,
                            "agent_message",
                            agent_id=agent.id,
                            payload={"to": next_agent_id, "preview": last_output[:300]},
                        )

            queue.extend(next_targets)
            context = f"{context}\n\n[{agent.name}]: {last_output}".strip()

        if steps >= max_steps:
            self._emit(
                run.id,
                "execution_guardrail",
                payload={"reason": "max steps reached", "max_steps": max_steps},
            )

        run.status = "completed"
        run.output_text = last_output
        run.completed_at = datetime.utcnow()
        self.db.commit()
        self._emit(run.id, "run_completed", payload={"output_preview": last_output[:500]})
        return last_output


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
