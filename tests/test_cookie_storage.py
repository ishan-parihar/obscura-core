"""Tests for the cookie storage backends in obscura_core.cookie_manager.storage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from obscura_core.cookie_manager.exceptions import CookieStorageError
from obscura_core.cookie_manager.storage import (
    BrowserProfileStorage,
    EnvVarCookieStorage,
    FileCookieStorage,
    MultiSourceCookieStorage,
)


@pytest.mark.asyncio
async def test_file_storage_roundtrip(tmp_path: Path) -> None:
    """save() then load() must return the same cookie dict."""
    store = FileCookieStorage(tmp_path / "cookies.json")
    original = {"session": "abc123", "user": "ishan"}
    await store.save(original)
    assert await store.load() == original


@pytest.mark.asyncio
async def test_file_storage_load_missing_returns_none(tmp_path: Path) -> None:
    """load() on a non-existent file returns None, not an error."""
    store = FileCookieStorage(tmp_path / "missing.json")
    assert await store.load() is None


@pytest.mark.asyncio
async def test_file_storage_sets_secure_permissions(tmp_path: Path) -> None:
    """Saved cookie files must be readable only by the owner."""
    store = FileCookieStorage(tmp_path / "cookies.json")
    await store.save({"k": "v"})
    mode = (tmp_path / "cookies.json").stat().st_mode & 0o777
    assert mode == 0o600


@pytest.mark.asyncio
async def test_file_storage_clear_removes_file(tmp_path: Path) -> None:
    """clear() must delete the cookie file."""
    store = FileCookieStorage(tmp_path / "cookies.json")
    await store.save({"k": "v"})
    await store.clear()
    assert not (tmp_path / "cookies.json").exists()


@pytest.mark.asyncio
async def test_file_storage_load_invalid_json_raises(tmp_path: Path) -> None:
    """Corrupt cookie files must raise CookieStorageError."""
    path = tmp_path / "cookies.json"
    path.write_text("{not valid json")
    store = FileCookieStorage(path)
    with pytest.raises(CookieStorageError):
        await store.load()


@pytest.mark.asyncio
async def test_file_storage_nested_format(tmp_path: Path) -> None:
    """Both {cookies: {...}} and flat {...} formats are accepted."""
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps({"cookies": {"a": "1"}}))
    store = FileCookieStorage(path)
    assert await store.load() == {"a": "1"}


@pytest.mark.asyncio
async def test_env_storage_loads_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """EnvVarCookieStorage parses a JSON dict cookie blob."""
    monkeypatch.setenv("OBSCURA_TEST_COOKIES", json.dumps({"a": "1", "b": "2"}))
    store = EnvVarCookieStorage("OBSCURA_TEST_COOKIES")
    assert await store.load() == {"a": "1", "b": "2"}


@pytest.mark.asyncio
async def test_env_storage_loads_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """EnvVarCookieStorage parses a list of {name, value} objects."""
    monkeypatch.setenv(
        "OBSCURA_TEST_COOKIES",
        json.dumps([{"name": "sid", "value": "x"}, {"name": "uid", "value": "y"}]),
    )
    store = EnvVarCookieStorage("OBSCURA_TEST_COOKIES")
    assert await store.load() == {"sid": "x", "uid": "y"}


@pytest.mark.asyncio
async def test_env_storage_empty_env_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing env var returns None."""
    monkeypatch.delenv("OBSCURA_TEST_COOKIES", raising=False)
    store = EnvVarCookieStorage("OBSCURA_TEST_COOKIES")
    assert await store.load() is None


@pytest.mark.asyncio
async def test_env_storage_invalid_json_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid JSON in the env var is ignored (returns None), not fatal."""
    monkeypatch.setenv("OBSCURA_TEST_COOKIES", "not-json")
    store = EnvVarCookieStorage("OBSCURA_TEST_COOKIES")
    assert await store.load() is None


@pytest.mark.asyncio
async def test_multi_source_priority(tmp_path: Path) -> None:
    """MultiSourceCookieStorage returns the first source that has cookies."""
    empty = FileCookieStorage(tmp_path / "empty.json")
    filled = FileCookieStorage(tmp_path / "filled.json")
    await filled.save({"k": "v"})
    multi = MultiSourceCookieStorage([empty, filled])
    assert await multi.load() == {"k": "v"}


@pytest.mark.asyncio
async def test_browser_profile_storage_roundtrip(tmp_path: Path) -> None:
    """BrowserProfileStorage persists cookies in profile format."""
    store = BrowserProfileStorage(tmp_path / "profile")
    await store.save({"sid": "v"})
    assert await store.load() == {"sid": "v"}
    assert store.profile_exists()


@pytest.mark.asyncio
async def test_exception_hierarchy() -> None:
    """All storage errors derive from ObscuraError."""
    from obscura_core.cookie_manager.exceptions import ObscuraError

    assert issubclass(CookieStorageError, ObscuraError)
