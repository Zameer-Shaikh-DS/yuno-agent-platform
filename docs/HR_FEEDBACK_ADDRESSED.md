# Yuno HR feedback — what was missing and what we fixed

Email from Yuno HR (Sreejita Saha) identified three gaps. This document maps each item to code changes for future submissions.

## 1. Schedule management

**Feedback:** UI/DB had schedule fields but no scheduler service executed cron/timezone jobs.

**Fix:**
- `app/services/scheduler.py` — APScheduler with `CronTrigger` + `ZoneInfo`
- Runs on API startup; reloads when agents are created/updated
- `GET /api/scheduler/jobs`, `POST /api/scheduler/reload`, `GET /api/scheduler/logs`
- Agent `schedule` JSON: `enabled`, `cron`, `timezone`, `input_template`, optional `workflow_id`

## 2. Guardrails and memory

**Feedback:** `blocked_topics` and memory window were UI-only; only summary was injected.

**Fix:**
- `app/services/guardrails.py` — blocks input/output matching `blocked_topics`
- `app/models/memory.py` + `app/services/memory_store.py` — persisted turns per agent
- `memory.window` loads last N user/assistant turns into the prompt (not summary-only)

## 3. Workflow feedback loops

**Feedback:** React Flow showed conditions but executor used topological order only (no cycles).

**Fix:**
- `app/runtime/executor.py` — graph traversal with `maxSteps` / `maxVisitsPerNode`
- Edge-level `condition` for branching (e.g. `contains:REVISE` loop back)
- Template **Quality Review Loop** seeded with Writer ↔ Reviewer cycle

## For next interview / resubmission

Demonstrate live:
1. Enable schedule on an agent → `GET /api/scheduler/jobs` shows next run
2. Set `blocked_topics` → run agent with blocked word → refusal
3. Chat twice with same agent → second run sees memory window in Monitor/logs
4. Run **Quality Review Loop** → Monitor shows `loop_limit_reached` or multiple writer steps
