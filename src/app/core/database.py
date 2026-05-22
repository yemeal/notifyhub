from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from src.app.core.settings import get_settings

settings = get_settings()

sync_engine = create_engine(
    url=settings.DATABASE_URL.replace("+asyncpg", ""),
    echo=settings.DEBUG,
)
SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
    expire_on_commit=False,
)


# def get_session() -> Generator[Session, None, None]:

async_engine = create_async_engine(
    url=settings.DATABASE_URL,
    echo=settings.DEBUG,
)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
