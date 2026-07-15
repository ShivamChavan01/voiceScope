import os
import pytest

os.environ["DATABASE_URL"] = ""

from unittest.mock import patch, AsyncMock, MagicMock
import storage.db as db_module


@pytest.fixture(autouse=True)
def reset_db_state():
    db_module._pool = None
    db_module._pool_lock = None
    yield
    db_module._pool = None


class TestGetPool:
    @pytest.mark.asyncio
    async def test_returns_none_without_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            result = await db_module.get_pool()
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_without_database_url_env(self):
        with patch.dict(os.environ, {}, clear=True):
            result = await db_module.get_pool()
            assert result is None

    @pytest.mark.asyncio
    async def test_creates_pool_with_database_url(self):
        mock_pool = AsyncMock()
        mock_pool._closed = False
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}):
            with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
                result = await db_module.get_pool()
                assert result is mock_pool

    @pytest.mark.asyncio
    async def test_reuses_existing_pool(self):
        mock_pool = AsyncMock()
        mock_pool._closed = False
        db_module._pool = mock_pool
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}):
            result = await db_module.get_pool()
            assert result is mock_pool

    @pytest.mark.asyncio
    async def test_creates_new_pool_if_closed(self):
        old_pool = AsyncMock()
        old_pool._closed = True
        db_module._pool = old_pool

        new_pool = AsyncMock()
        new_pool._closed = False
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}):
            with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=new_pool):
                result = await db_module.get_pool()
                assert result is new_pool
                assert result is not old_pool


class TestClosePool:
    @pytest.mark.asyncio
    async def test_close_pool_with_active_pool(self):
        mock_pool = AsyncMock()
        mock_pool._closed = False
        db_module._pool = mock_pool
        await db_module.close_pool()
        mock_pool.close.assert_called_once()
        assert db_module._pool is None

    @pytest.mark.asyncio
    async def test_close_pool_already_closed(self):
        mock_pool = AsyncMock()
        mock_pool._closed = True
        db_module._pool = mock_pool
        await db_module.close_pool()
        mock_pool.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_pool_none(self):
        db_module._pool = None
        await db_module.close_pool()
        assert db_module._pool is None


class TestInitSchema:
    @pytest.mark.asyncio
    async def test_init_schema_no_pool(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            await db_module.init_schema()

    @pytest.mark.asyncio
    async def test_init_schema_with_pool(self):
        from unittest.mock import MagicMock
        mock_pool = MagicMock()
        mock_pool._closed = False
        mock_conn = AsyncMock()
        # pool.acquire() returns an async context manager (not a coroutine)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_ctx
        db_module._pool = mock_pool
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            await db_module.init_schema()
        mock_conn.execute.assert_called_once()
