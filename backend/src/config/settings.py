"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # 品牌与业务
    brand: str = "docflow"
    org_name: str = "恒安保险经纪 · 理赔受理组"
    archive_store: str = "archive_store"

    # 数据库
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "docflow"
    db_user: str = "docflow"
    db_password: str = "docflow_pw_2026"
    db_schema: str = "docflow"

    # 安全
    jwt_secret: str = "docflow-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120

    # 运行时
    redis_url: str = "redis://localhost:6379/0"
    seed_demo: bool = True
    login_attempt_per_minute: int = 12
    rate_limit_run_per_minute: int = 8
    rate_limit_confirm_per_minute: int = 40
    rate_limit_default_per_minute: int = 300

    # 算法阈值（与 fixtures 一起可复现；前端只展示后端回传值）
    pending_confidence_threshold: float = 0.60
    duplicate_seq_limit: int = 99

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
