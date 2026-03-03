from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.routers import agents, auth, debates, graph, theses, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.utils.ws_manager import ws_manager
    await ws_manager.connect_redis()
    yield
    await engine.dispose()


app = FastAPI(
    title="Knowledge Arena",
    version="1.1.0",
    description="Structured AI debate platform with epistemological protocols",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
