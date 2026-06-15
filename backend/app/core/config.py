from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/study_planner"
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 90

    # AI / LLM
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    LLM_TEMPERATURE: float = 0.2

    # RAG
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    FAISS_INDEX_DIR: str = "data/faiss"
    RAG_TOP_K: int = 4
    # Max FAISS L2 distance (on normalized embeddings) to count a chunk as
    # relevant. Chunks farther than this are dropped so off-topic questions
    # fall back to the grounded "no relevant info" answer.
    RAG_SCORE_THRESHOLD: float = 1.5

    model_config = {"env_file": ".env"}


settings = Settings()
