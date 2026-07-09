from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    ocr_language: str = "eng"
    render_dpi: int = 150
    min_confidence: int = 35
    max_upload_mb: int = 25
    max_pages: int = 5
    ocr_timeout_seconds: int = 20
    ocr_pages_with_embedded_text: bool = False
    mds_library_module: str | None = None
    mds_endpoint: str | None = None
    mds_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")
