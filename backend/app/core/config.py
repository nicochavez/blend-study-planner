import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/study_planner"
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 90

    # AI / LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "dev-key-change-in-production")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    LLM_TEMPERATURE: float = 0.2
    # Per-response output cap. Must be generous: the planning agent emits the
    # full task list in one submit_plan tool call, and a low cap truncates it
    # mid-call and sends the deep-agent loop into a retry spiral. Kept below
    # ~16k so non-streaming agent.invoke calls stay under the SDK timeout.
    LLM_MAX_TOKENS: int = 8192

    # RAG
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    FAISS_INDEX_DIR: str = "data/faiss"
    RAG_TOP_K: int = 4
    # Max FAISS L2 distance (on normalized embeddings) to count a chunk as
    # relevant. Chunks farther than this are dropped so off-topic questions
    # fall back to the grounded "no relevant info" answer.
    RAG_SCORE_THRESHOLD: float = 1.5

    # Planning agent
    # Horizon (in weeks) used to size the hours budget when a plan has no
    # target_date.
    DEFAULT_PLAN_WEEKS: int = 8
    # Fractional tolerance allowed over the hours budget before the
    # constraint validator flags a plan as over-budget.
    PLAN_HOURS_TOLERANCE: float = 0.1
    # Max number of subtopics the planning agent may break a goal into.
    AGENT_MAX_SUBTOPICS: int = 12
    # Caps the planning agent's tool-call loop so a confused agent can't run
    # away.
    AGENT_RECURSION_LIMIT: int = 50

    model_config = {"env_file": ".env"}


settings = Settings()
