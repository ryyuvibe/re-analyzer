"""FastAPI dependency injection."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config import settings
from src.data.rentcast import RentCastClient
from src.data.fred import FREDClient
from src.data.resolver import PropertyResolver

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def get_resolver() -> PropertyResolver:
    return PropertyResolver(RentCastClient())


def get_fred_client() -> FREDClient:
    return FREDClient()
