import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db, SessionLocal
from .api import api_router
from .api.monitor import router as monitor_router
from .seed import seed_database
from .channels.telegram_bot import start_telegram_bot, stop_telegram_bot
from .services.monitor_hub import monitor_hub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yuno")


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_hub.set_loop(asyncio.get_running_loop())
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    await start_telegram_bot()
    yield
    await stop_telegram_bot()


settings = get_settings()
app = FastAPI(title="Yuno Agent Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(monitor_router)


@app.get("/health")
def health():
    from .llm_provider import resolve_llm_config
    llm = resolve_llm_config(
        api_key=settings.llm_api_key,
        mock_llm=settings.mock_llm,
        provider_override=settings.llm_provider,
    )
    return {
        "status": "ok",
        "mock_llm": settings.mock_llm,
        "llm_provider": llm.provider,
        "llm_model": llm.default_model,
        "llm_configured": bool(llm.api_key) or settings.mock_llm,
    }


@app.get("/api/health")
def api_health():
    return health()
