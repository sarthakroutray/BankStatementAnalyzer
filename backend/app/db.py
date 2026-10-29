from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    pass


def get_engine_and_maker(db_url: str | None = None) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    raw_url = db_url or settings.DATABASE_URL
    is_postgres = raw_url.startswith("postgresql+asyncpg://") or raw_url.startswith("postgresql://")

    connect_args: dict[str, object] = {}
    cleaned_url = raw_url

    if is_postgres:
        parsed = urlparse(raw_url)
        query_params = parse_qs(parsed.query)

        # asyncpg prefers ssl parameter via connect_args rather than ?sslmode=require in query
        if "sslmode" in query_params:
            sslmode_val = query_params.pop("sslmode")[0]
            if sslmode_val.lower() in ("disable", "allow", "prefer"):
                connect_args["ssl"] = False
            else:
                connect_args["ssl"] = "require"
        elif "ssl" in query_params:
            ssl_val = query_params.pop("ssl")[0]
            if ssl_val.lower() in ("true", "require", "1"):
                connect_args["ssl"] = "require"
            else:
                connect_args["ssl"] = False
        else:
            connect_args["ssl"] = "require"

        # Parameters unsupported by asyncpg that are commonly appended by Neon or libpq connection strings
        unsupported_asyncpg_params = [
            "channel_binding",
            "endpoint",
            "gssencmode",
            "sslcompression",
            "target_session_attrs",
        ]
        for param in unsupported_asyncpg_params:
            query_params.pop(param, None)

        new_query = urlencode(query_params, doseq=True)
        cleaned_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        # Use NullPool for Neon serverless PgBouncer pooler
        engine = create_async_engine(
            cleaned_url,
            poolclass=NullPool,
            connect_args=connect_args,
            echo=False,
            future=True,
        )
    else:
        # SQLite or other test dialects
        engine = create_async_engine(
            cleaned_url,
            echo=False,
            future=True,
        )

    session_maker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
        class_=AsyncSession,
    )
    return engine, session_maker


engine, AsyncSessionLocal = get_engine_and_maker()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db(engine_instance: AsyncEngine | None = None) -> None:
    eng = engine_instance or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
