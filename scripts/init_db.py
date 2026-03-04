"""Database initialization script.

Tries alembic upgrade head first. If that fails for any reason,
falls back to SQLAlchemy Base.metadata.create_all() so the app
can at least start with all tables present.
"""
import asyncio
import subprocess
import sys


def try_alembic():
    """Run alembic upgrade head, return True if successful."""
    print("[init_db] Running alembic upgrade head...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, flush=True)
    if result.returncode == 0:
        print("[init_db] Alembic migration succeeded.", flush=True)
        return True
    else:
        print(f"[init_db] Alembic failed with exit code {result.returncode}", flush=True)
        return False


async def fallback_create_all():
    """Create all tables using SQLAlchemy metadata as fallback."""
    print("[init_db] Falling back to Base.metadata.create_all()...", flush=True)
    from app.database import engine
    from app.models.base import Base

    # Import all models so they register with Base.metadata
    import app.models.user  # noqa: F401
    import app.models.agent  # noqa: F401
    import app.models.debate  # noqa: F401
    import app.models.thesis  # noqa: F401
    import app.models.voting  # noqa: F401
    import app.models.graph  # noqa: F401
    import app.models.evaluation  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("[init_db] create_all() completed successfully.", flush=True)


def main():
    if not try_alembic():
        try:
            asyncio.run(fallback_create_all())
        except Exception as e:
            print(f"[init_db] FATAL: fallback create_all() also failed: {e}", flush=True)
            sys.exit(1)
    print("[init_db] Database initialization complete.", flush=True)


if __name__ == "__main__":
    main()
