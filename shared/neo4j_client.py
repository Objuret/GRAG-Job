"""Thin async wrapper around the Neo4j driver."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from neo4j import AsyncGraphDatabase, AsyncSession

from .config import Settings


class Neo4jClient:
    def __init__(self, settings: Settings) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._database = settings.neo4j_database

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._driver.session(database=self._database) as session:
            yield session

    async def close(self) -> None:
        await self._driver.close()
