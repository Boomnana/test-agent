from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

class Settings(BaseSettings):
    PROJECT_NAME: str = "Test Report Agent"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./test_report.db"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # LLM
    LLM_API_KEY: str
    LLM_MODEL: str = "glm-4-air"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 10000
    LLM_CONCURRENCY: int = 20
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 2

    # Auth
    JWT_SECRET_KEY: str = "change_me_dev_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=os.path.join(BASE_DIR, ".env"), env_file_encoding='utf-8', case_sensitive=True, extra='ignore')

settings = Settings()
