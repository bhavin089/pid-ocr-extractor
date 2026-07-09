from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    ocr_language: str = "eng"
    render_dpi: int = 220
    min_confidence: int = 35
    mds_library_module: str | None = None
    mds_endpoint: str | None = None
    mds_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

