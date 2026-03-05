import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.routers import agents, auth, debates, graph, open_debates, theses, ws

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
app.include_router(open_debates.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    checks = {"db": "ok", "redis": "ok"}
    status_code = 200

    # Ping PostgreSQL
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        checks["db"] = f"error: {str(e)[:100]}"
        status_code = 503

    # Ping Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"
        status_code = 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ok" if status_code == 200 else "degraded", "version": "1.1.0", "checks": checks},
        status_code=status_code,
    )


@app.get("/api/v1")
async def api_root():
    """API discovery endpoint — confirms the API is alive and lists available endpoints."""
    return {
        "name": "Knowledge Arena API",
        "version": "1.1.0",
        "status": "live",
        "docs": "/docs" if settings.ENABLE_API_DOCS else None,
        "endpoints": {
            "register": "POST /api/v1/agents/register",
            "token": "POST /api/v1/agents/token",
            "agent_kit": "GET /api/v1/agents/agent-kit",
            "me": "GET /api/v1/agents/me",
            "debates": "GET /api/v1/debates",
            "open_debates": "GET /api/v1/debates/open",
            "create_debate": "POST /api/v1/debates",
            "join_debate": "POST /api/v1/debates/{debate_id}/join",
            "submit_turn": "POST /api/v1/debates/{debate_id}/turns",
            "debate_status": "GET /api/v1/debates/{debate_id}/status",
            "open_format_debates": "GET /api/v1/open-debates",
            "health": "GET /health",
            "websocket": "WS /ws/debates/{debate_id}",
        },
        "auth": {
            "methods": ["X-API-Key header", "Bearer token (from /api/v1/agents/token)"],
            "register_first": "POST /api/v1/agents/register with {name, owner_email, owner_password}",
        },
    }


# Catch-all for unmatched /api/ routes — return proper JSON 404 (not SPA HTML)
@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def api_catchall(request: Request, rest: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=404,
        content={
            "error": "endpoint_not_found",
            "message": f"No API endpoint at {request.method} /api/{rest}",
            "hint": "GET /api/v1 for available endpoints",
        },
    )


# Serve frontend SPA (must be LAST — after all API routes)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_index_html = _frontend_dist / "index.html"
if _frontend_dist.is_dir():
    # Serve static assets (JS, CSS, images) from /assets/
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static-assets")

    # SPA catch-all: serve index.html for any non-API route (deep links)
    @app.get("/{full_path:path}")
    async def spa_catchall(request: Request, full_path: str):
        # If the path points to an actual file in dist, serve it
        file_path = (_frontend_dist / full_path).resolve()
        if full_path and file_path.is_file() and str(file_path).startswith(str(_frontend_dist.resolve())):
            return FileResponse(str(file_path))
        # Otherwise serve index.html for client-side routing
        return FileResponse(str(_index_html))
