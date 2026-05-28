import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from ..config import get_settings
from ..database import SessionLocal
from ..models.agent import Agent
from ..models.workflow import Workflow
from ..runtime.agent_factory import run_agent
from ..runtime.executor import WorkflowExecutor
from ..models.run import WorkflowRun

logger = logging.getLogger("telegram")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yuno Agent Platform\n\n"
        "Commands:\n"
        "/agents - list agents\n"
        "/run <workflow_name> <query> - run a workflow\n"
        "Or send any message to chat with the gateway agent."
    )


async def agents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        agents = db.query(Agent).all()
        lines = [f"- {a.name} ({a.id[:8]}...)" for a in agents]
        await update.message.reply_text("Agents:\n" + "\n".join(lines) if lines else "No agents")
    finally:
        db.close()


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /run <workflow_name> <your query>")
        return

    wf_name = context.args[0].lower()
    query = " ".join(context.args[1:])

    db = SessionLocal()
    try:
        wf = db.query(Workflow).filter(Workflow.name.ilike(f"%{wf_name}%")).first()
        if not wf:
            await update.message.reply_text(f"Workflow '{wf_name}' not found.")
            return

        run = WorkflowRun(workflow_id=wf.id, input_text=query, status="pending")
        db.add(run)
        db.commit()
        db.refresh(run)

        agent_ids = {
            n.get("data", {}).get("agentId")
            for n in wf.definition.get("nodes", [])
            if n.get("data", {}).get("agentId")
        }
        agents_list = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
        agents = {a.id: a for a in agents_list}

        await update.message.reply_text(f"Running workflow '{wf.name}'...")

        loop = asyncio.get_running_loop()
        executor = WorkflowExecutor(db)
        output = await loop.run_in_executor(None, executor.execute, wf, run, agents)

        await update.message.reply_text(output[:4000])
    except Exception:
        logger.exception("run_command failed")
        await update.message.reply_text("An error occurred while running the workflow.")
    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    db = SessionLocal()
    try:
        settings = get_settings()
        agent = None
        if settings.telegram_default_agent_id:
            agent = db.query(Agent).filter(Agent.id == settings.telegram_default_agent_id).first()
        if not agent:
            agent = db.query(Agent).filter(Agent.is_gateway == True).first()  # noqa: E712
        if not agent:
            agent = db.query(Agent).first()
        if not agent:
            await update.message.reply_text("No agents configured.")
            return

        await update.message.reply_text("Thinking...")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_agent, agent, text)
        await update.message.reply_text(result["response"][:4000])
    except Exception:
        logger.exception("handle_message failed")
        await update.message.reply_text("An error occurred while processing your message.")
    finally:
        db.close()


def build_telegram_app() -> Application | None:
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        return None
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("agents", agents_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


_telegram_app: Application | None = None


async def start_telegram_bot():
    global _telegram_app
    _telegram_app = build_telegram_app()
    if not _telegram_app:
        logger.info("Telegram bot disabled (no TELEGRAM_BOT_TOKEN)")
        return
    await _telegram_app.initialize()
    await _telegram_app.start()
    await _telegram_app.updater.start_polling()
    logger.info("Telegram bot started")


async def stop_telegram_bot():
    global _telegram_app
    if _telegram_app:
        await _telegram_app.updater.stop()
        await _telegram_app.stop()
        await _telegram_app.shutdown()
        _telegram_app = None
