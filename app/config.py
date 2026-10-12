from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://qa:qa@localhost:5440/qa"
    database_pool_size: int = Field(default=5, ge=1)
    database_timeout_seconds: int = Field(default=10, ge=1)

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "qa_questions"
    qdrant_timeout_seconds: int = Field(default=30, ge=1)

    embedding_model: str = "BAAI/bge-m3"
    embedding_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    embedding_device: str = "cpu"
    embedding_batch_size: int = Field(default=32, ge=1)
    embedding_max_length: int = Field(default=512, ge=16)

    search_candidates: int = Field(default=20, ge=1, le=200)
    search_top_k: int = Field(default=5, ge=1, le=50)
    match_threshold: float = Field(default=0.67, ge=0.0, le=1.0)
    ambiguity_margin: float = Field(default=0.02, ge=0.0, le=1.0)
    ambiguity_max_words: int = Field(default=2, ge=0)

    max_upload_mb: int = Field(default=10, ge=1)
    log_level: str = "INFO"
    log_questions: bool = True
