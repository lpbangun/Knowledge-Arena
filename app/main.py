import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.routers import agents, auth, debates, graph, theses, ws

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start with the default dev JWT key in production
    if settings.is_dev_jwt_key:
        logger.warning(
            "JWT_SECRET_KEY is set to the default dev key. "
            "Set a strong JWT_SECRET_KEY env var before deploying to production."
        )
    from app.utils.ws_manager import ws_manager
    await ws_manager.connect_redis()
    yield
    await engine.dispose()


docs_url = "/docs" if settings.ENABLE_API_DOCS else None
redoc_url = "/redoc" if settings.ENABLE_API_DOCS else None

app = FastAPI(
    title="Knowledge Arena",
    version="1.1.0",
    description="Structured AI debate platform with epistemological protocols",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(agents.router)
app.include_router(debates.router)
app.include_router(auth.router)
app.include_router(graph.router)
app.include_router(theses.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}


# Serve frontend SPA (must be LAST — after all API routes)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="spa")
