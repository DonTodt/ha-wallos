"""Async API client for Wallos."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class WallosApiError(Exception):
    """Generic API error."""


class WallosAuthError(WallosApiError):
    """Invalid API key."""


class WallosConnectionError(WallosApiError):
    """Server not reachable."""


class WallosApiClient:
    """Thin client around the Wallos REST API (GET endpoints only)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._verify_ssl = verify_ssl

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        # Some endpoints document `apiKey`, others `api_key` -> send both.
        query = {"api_key": self._api_key, "apiKey": self._api_key, **(params or {})}
        kwargs: dict[str, Any] = {} if self._verify_ssl else {"ssl": False}
        try:
            async with asyncio.timeout(30):
                async with self._session.get(
                    f"{self._base_url}{path}", params=query, **kwargs
                ) as resp:
                    if resp.status in (401, 403):
                        raise WallosAuthError("Invalid API key")
                    if resp.status >= 400:
                        raise WallosApiError(f"HTTP {resp.status}")
                    data = await resp.json(content_type=None)
        except WallosApiError:
            raise
        except TimeoutError as err:
            raise WallosConnectionError("Timeout") from err
        except aiohttp.ClientError as err:
            raise WallosConnectionError("Connection failed") from err
        except ValueError as err:
            raise WallosApiError("Response is not valid JSON") from err

        if not isinstance(data, dict):
            raise WallosApiError("Unexpected response")
        if data.get("success") is False:
            text = f"{data.get('title', '')} {data.get('notes', '')}".lower()
            if "unauthorized" in text or "api key" in text:
                raise WallosAuthError("Invalid API key")
            raise WallosApiError(str(data.get("title") or "Request failed"))
        return data

    async def get_user(self) -> dict[str, Any]:
        return (await self._get("/api/users/get_user.php")).get("user") or {}

    async def get_currencies(self) -> dict[str, Any]:
        return await self._get("/api/currencies/get_currencies.php")

    async def get_subscriptions(self, convert_currency: bool) -> list[dict[str, Any]]:
        data = await self._get(
            "/api/subscriptions/get_subscriptions.php",
            {"convert_currency": "true" if convert_currency else "false"},
        )
        return data.get("subscriptions") or []

    async def get_monthly_cost(self, month: int, year: int) -> dict[str, Any]:
        return await self._get(
            "/api/subscriptions/get_monthly_cost.php", {"month": month, "year": year}
        )
