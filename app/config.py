from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://knowledge:knowledge@localhost:5432/knowledge_arena"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenRouter API
    OPENROUTER_API_KEY: str = "sk-or-placeholder"

    # Arbiter model config
    ARBITER_LAYER1_MODEL: str = "deepseek/deepseek-v3.2"
    ARBITER_LAYER2_MODEL: str = "moonshotai/kimi-k2.5"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key-not-for-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Public URL — canonical base URL for API discovery (agents need this)
    PUBLIC_URL: str = "https://knowledge-arena.up.railway.app"

    # CORS — comma-separated origins (include production domain)
    ALLOWED_ORIGINS: str = "http://localhost:5173,https://knowledgearena.ai,https://www.knowledgearena.ai"

    # API docs (enabled by default — agents need discovery)
    ENABLE_API_DOCS: bool = True

    # Platform config
    DEFAULT_MAX_ROUNDS: int = 10
    DEFAULT_PHASE0_MAX_ROUNDS: int = 3
    DEFAULT_CITATION_CHALLENGES_DEBATER: int = 3
    DEFAULT_CITATION_CHALLENGES_AUDIENCE: int = 1
    DEFAULT_AMICUS_BRIEFS_PER_AUDIENCE: int = 2
    MAX_AGENTS_PER_DEBATE: int = 6
    STANDING_THESIS_DAYS: int = 30
    MIN_ELO_ACCEPT_CHALLENGE: int = 800
    MIN_ELO_GAP_DETECTION: int = 1200
    MAX_TURN_CONTENT_CHARS: int = 50000
    MAX_TOULMIN_TAGS: int = 50

    # Open debates
    OPEN_DEBATE_DURATION_HOURS: int = 24
    OPEN_DEBATE_GENERATE_WITH_LLM: bool = False

    # Phase 0 timeout (seconds) — how long to wait for stragglers before majority activation
    PHASE_0_TIMEOUT_SECONDS: int = 60

    # Feature flags
    ENABLE_PGVECTOR: bool = False
    ARBITER_ROTATION_ENABLED: bool = False
    AUTO_VALIDATE_TURNS: bool = True  # Auto-validate turns (no arbiter dependency for MVP)

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev_jwt_key(self) -> bool:
        return self.JWT_SECRET_KEY == "dev-secret-key-not-for-production"


settings = Settings()
