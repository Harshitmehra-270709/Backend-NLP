from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class AppSettings:
    app_name: str
    app_version: str
    app_secret_key: str
    gemini_api_key: str
    parser_mode: str
    allowed_origins: list[str]
    command_db_path: str
    request_rate_limit: int
    rate_limit_window_seconds: int
    execution_delay_seconds: float

    @classmethod
    def from_env(cls) -> "AppSettings":
        root_path = Path(__file__).resolve().parent.parent
        default_db_path = root_path / "data" / "command_center.db"
        default_db_path.parent.mkdir(parents=True, exist_ok=True)

        allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
        return cls(
            app_name=os.getenv("APP_NAME", "AI Command Control Center"),
            app_version=os.getenv("APP_VERSION", "2.0.0"),
            app_secret_key=os.getenv("APP_SECRET_KEY", "dev-secret-key-123"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            parser_mode=os.getenv("PARSER_MODE", "auto").strip().lower(),
            allowed_origins=[
                origin.strip()
                for origin in allowed_origins.split(",")
                if origin.strip()
            ],
            command_db_path=os.getenv("COMMAND_DB_PATH", str(default_db_path)),
            request_rate_limit=int(os.getenv("REQUEST_RATE_LIMIT", "60")),
            rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
            execution_delay_seconds=float(os.getenv("EXECUTION_DELAY_SECONDS", "0.2")),
        )
