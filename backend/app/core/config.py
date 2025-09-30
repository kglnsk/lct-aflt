from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, ValidationError


class AppConfig(BaseModel):
    """Runtime configuration for the backend service."""

    app_name: str = "ToolKit Vision API"
    detection_service_url: Optional[HttpUrl] = Field(
        default=None,
        description="Base URL of the external detection service (e.g. YOLO API).",
    )
    detection_timeout_seconds: float = Field(
        default=8.0,
        description="Timeout for detection service requests.",
    )
    upload_dir: Path = Field(
        default=Path("data/uploads"),
        description="Directory where uploaded images are stored.",
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS origins allowed to access the API.",
    )
    database_url: str = Field(
        default="sqlite:///data/app.db",
        description="SQLAlchemy database URL (defaults to SQLite file).",
    )
    initial_admin_username: str = Field(
        default="admin",
        description="Username for the bootstrap admin account.",
    )
    initial_admin_password: str = Field(
        default="admin123",
        description="Password for the bootstrap admin account.",
    )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration values from environment variables."""
        raw_upload_dir = os.getenv("UPLOAD_DIR")
        raw_allowed_origins = os.getenv("ALLOWED_ORIGINS")
        data = {
            "detection_service_url": os.getenv("DETECTION_SERVICE_URL"),
            "detection_timeout_seconds": os.getenv("DETECTION_TIMEOUT_SECONDS"),
            "database_url": os.getenv("DATABASE_URL"),
            "initial_admin_username": os.getenv("INITIAL_ADMIN_USERNAME"),
            "initial_admin_password": os.getenv("INITIAL_ADMIN_PASSWORD"),
        }
        if raw_upload_dir:
            data["upload_dir"] = Path(raw_upload_dir)
        if raw_allowed_origins:
            data["allowed_origins"] = [
                item.strip()
                for item in raw_allowed_origins.split(",")
                if item.strip()
            ]
        config = cls.parse_obj(data)
        config.upload_dir.mkdir(parents=True, exist_ok=True)
        if config.database_url.startswith("sqlite"):
            db_path = config.database_url.split("sqlite:///")[-1]
            if db_path:
                Path(db_path).expanduser().resolve(strict=False).parent.mkdir(
                    parents=True, exist_ok=True
                )
        return config


@lru_cache
def get_config() -> AppConfig:
    """Return cached application configuration."""
    try:
        return AppConfig.from_env()
    except ValidationError:
        # In case of invalid env config, fall back to defaults while keeping directory creation.
        config = AppConfig()
        config.upload_dir.mkdir(parents=True, exist_ok=True)
        return config
