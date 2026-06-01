"""Cron + timezone scheduler — executes enabled agent schedules."""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..database import SessionLocal
from ..models.agent import Agent
from ..models.schedule_log import ScheduledRunLog
from ..runtime.agent_factory import run_agent

logger = logging.getLogger("yuno.scheduler")


class AgentSchedulerService:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._started = False

    def start(self) -> None:
        # TestClient starts/stops app multiple times; reset scheduler safely each startup.
        if self._started:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                logger.exception("Scheduler shutdown during restart failed")
            finally:
                self._started = False
        self._scheduler = AsyncIOScheduler()
        try:
            self._scheduler.start()
            self._started = True
        except RuntimeError:
            # Called outside a running event loop (e.g. direct unit tests)
            logger.info("Scheduler start skipped: no running event loop")
            self._started = False
            return
        self.reload_jobs()

    def shutdown(self) -> None:
        if self._started:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                logger.exception("Scheduler shutdown failed")
            self._started = False

    def reload_jobs(self) -> None:
        if not self._started:
            return
        self._scheduler.remove_all_jobs()
        db = SessionLocal()
        try:
            agents = db.query(Agent).all()
            for agent in agents:
                sched = agent.schedule or {}
                if not sched.get("enabled"):
                    continue
                cron = (sched.get("cron") or "").strip()
                if not cron:
                    logger.warning("Agent %s: schedule enabled but no cron", agent.name)
                    continue
                tz_name = sched.get("timezone") or "UTC"
                try:
                    tz = ZoneInfo(tz_name)
                except Exception:
                    logger.warning("Invalid timezone %s for agent %s, using UTC", tz_name, agent.name)
                    tz = ZoneInfo("UTC")
                self._scheduler.add_job(
                    self._execute_scheduled_agent,
                    CronTrigger.from_crontab(cron, timezone=tz),
                    id=f"agent-schedule-{agent.id}",
                    args=[agent.id],
                    replace_existing=True,
                    misfire_grace_time=300,
                )
                logger.info("Scheduled agent '%s' cron=%s tz=%s", agent.name, cron, tz_name)
        finally:
            db.close()

    async def _execute_scheduled_agent(self, agent_id: str) -> None:
        db = SessionLocal()
        log = ScheduledRunLog(agent_id=agent_id, status="running")
        db.add(log)
        db.commit()
        try:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                log.status = "failed"
                log.error = "Agent not found"
                db.commit()
                return

            sched = agent.schedule or {}
            prompt = sched.get("input_template") or sched.get("prompt") or "Execute your scheduled task."
            workflow_id = sched.get("workflow_id")

            if workflow_id:
                from ..models.workflow import Workflow
                from ..models.run import WorkflowRun
                from ..runtime.executor import WorkflowExecutor

                wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
                if not wf:
                    raise ValueError(f"Workflow {workflow_id} not found")
                run = WorkflowRun(workflow_id=workflow_id, input_text=prompt, status="pending")
                db.add(run)
                db.commit()
                db.refresh(run)
                agent_ids = {
                    n.get("data", {}).get("agentId")
                    for n in wf.definition.get("nodes", [])
                    if n.get("data", {}).get("agentId")
                }
                agents_list = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
                agents_map = {a.id: a for a in agents_list}
                output = WorkflowExecutor(db).execute(wf, run, agents_map)
            else:
                result = run_agent(agent, prompt, db=db)
                output = result.get("response", "")

            log.status = "completed"
            log.input_text = prompt
            log.output_text = str(output)[:8000]
            db.commit()
            logger.info("Scheduled run completed for agent %s", agent.name)
        except Exception as exc:
            logger.exception("Scheduled run failed for agent %s", agent_id)
            log.status = "failed"
            log.error = str(exc)
            db.commit()
        finally:
            db.close()

    def list_jobs(self) -> list[dict]:
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
            )
        return jobs


agent_scheduler = AgentSchedulerService()


class _SchedulerLifecycle:
    """Async lifespan wrapper for FastAPI."""

    async def start(self) -> None:
        agent_scheduler.start()

    async def stop(self) -> None:
        agent_scheduler.shutdown()


scheduler_service = _SchedulerLifecycle()
