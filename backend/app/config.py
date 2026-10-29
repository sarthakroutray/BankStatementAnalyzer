from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./bank_analyzer.db"
    FRONTEND_URL: Union[str, List[str]] = "http://localhost:3000"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api/v1"
    DEFAULT_SARIMA_HORIZON: int = 30
    CONFIDENCE_ALPHA: float = 0.10  # 90% confidence intervals

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not v:
            return "sqlite+aiosqlite:///./bank_analyzer.db"
        v_str = str(v).strip()
        # Handle Neon / standard postgres schemes for asyncpg
        if v_str.startswith("postgres://"):
            v_str = "postgresql+asyncpg://" + v_str[len("postgres://"):]
        elif v_str.startswith("postgresql://") and not v_str.startswith("postgresql+asyncpg://"):
            v_str = "postgresql+asyncpg://" + v_str[len("postgresql://"):]

        # Strip unsupported asyncpg parameters like channel_binding from URL query
        if "postgresql+asyncpg://" in v_str and "?" in v_str:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(v_str)
            params = parse_qs(parsed.query)
            changed = False
            for p in ["channel_binding", "endpoint", "gssencmode", "sslcompression"]:
                if p in params:
                    params.pop(p, None)
                    changed = True
            if changed:
                new_query = urlencode(params, doseq=True)
                v_str = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
        return v_str

    @property
    def cors_origins(self) -> List[str]:
        if isinstance(self.FRONTEND_URL, list):
            return self.FRONTEND_URL
        if self.FRONTEND_URL == "*":
            return ["*"]
        origins = [orig.strip() for orig in self.FRONTEND_URL.split(",") if orig.strip()]
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins


settings = Settings()
