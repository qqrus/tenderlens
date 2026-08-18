from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tenderlens.db.session import Database


class FakeConnection:
    def __init__(self) -> None:
        self.executed = False

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        self.executed = True


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    async def dispose(self) -> None:
        self.disposed = True


@pytest.mark.asyncio
async def test_database_ping_and_close() -> None:
    fake_engine = FakeEngine()
    database = cast(Any, Database.__new__(Database))
    database.engine = cast(AsyncEngine, fake_engine)

    await database.ping()
    await database.close()

    assert fake_engine.connection.executed is True
    assert fake_engine.disposed is True
