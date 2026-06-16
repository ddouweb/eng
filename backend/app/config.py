from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:root123@localhost:3306/english_coach?charset=utf8mb4"
    AI_PROVIDER: str = "claude"
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = "admin123"
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_EXPIRE_MINUTES: int = 1440

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
