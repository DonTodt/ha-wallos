"""Data update coordinator for Wallos."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WallosApiClient, WallosApiError, WallosAuthError
from .const import (
    CONF_CONVERT_CURRENCY,
    CONF_DUE_SOON_DAYS,
    CONF_PER_SUBSCRIPTION,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONVERT_CURRENCY,
    DEFAULT_DUE_SOON_DAYS,
    DEFAULT_PER_SUBSCRIPTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .models import WallosCurrency, WallosData, WallosSubscription, _to_float, _to_int

_LOGGER = logging.getLogger(__name__)

type WallosConfigEntry = ConfigEntry[WallosCoordinator]


class WallosCoordinator(DataUpdateCoordinator[WallosData]):
    """Fetches all Wallos data."""

    config_entry: WallosConfigEntry

    def __init__(self, hass: HomeAssistant, entry: WallosConfigEntry, client: WallosApiClient) -> None:
        opts = entry.options
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=int(opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            ),
        )
        self.client = client
        self.convert_currency: bool = opts.get(CONF_CONVERT_CURRENCY, DEFAULT_CONVERT_CURRENCY)
        self.due_soon_days = int(opts.get(CONF_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS))
        self.per_subscription: bool = opts.get(CONF_PER_SUBSCRIPTION, DEFAULT_PER_SUBSCRIPTION)

    @property
    def hub_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name="Wallos",
            manufacturer="Wallos",
            model="Subscription Tracker",
            configuration_url=self.config_entry.data[CONF_URL],
        )

    @callback
    def ensure_hub_device(self) -> dr.DeviceEntry:
        """Create (or update) the hub device and return it."""
        return dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name="Wallos",
            manufacturer="Wallos",
            model="Subscription Tracker",
            configuration_url=self.config_entry.data[CONF_URL],
        )

    @callback
    def ensure_subscription_device(self, sub: WallosSubscription) -> dr.DeviceEntry:
        """Create (or update) the device of a subscription, linked to the hub.

        Uses `via_device_id` (device registry id) instead of the deprecated
        `via_device` identifier tuple.
        """
        hub = self.ensure_hub_device()
        url = sub.url if sub.url and sub.url.startswith(("http://", "https://")) else None
        return dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, f"{self.config_entry.entry_id}_sub_{sub.id}")},
            name=sub.name,
            manufacturer="Wallos",
            model=sub.category or "Subscription",
            via_device_id=hub.id,
            configuration_url=url,
        )

    async def _async_update_data(self) -> WallosData:
        try:
            user = await self.client.get_user()
            cur_data = await self.client.get_currencies()
            raw_subs = await self.client.get_subscriptions(self.convert_currency)
            now = dt_util.now()
            try:
                month_cost = await self.client.get_monthly_cost(now.month, now.year)
            except WallosAuthError:
                raise
            except WallosApiError as err:
                _LOGGER.debug("Monthly cost not available: %s", err)
                month_cost = None
        except WallosAuthError as err:
            raise ConfigEntryAuthFailed("Invalid Wallos API key") from err
        except WallosApiError as err:
            raise UpdateFailed(f"Error talking to Wallos: {err}") from err

        currencies: dict[int, WallosCurrency] = {}
        for raw in cur_data.get("currencies") or []:
            cid = _to_int(raw.get("id"))
            if cid is None:
                continue
            currencies[cid] = WallosCurrency(
                id=cid,
                code=str(raw.get("code") or ""),
                symbol=str(raw.get("symbol") or ""),
                name=str(raw.get("name") or ""),
                rate=_to_float(raw.get("rate"), 1.0),
            )
        main_id = _to_int(cur_data.get("main_currency")) or _to_int(user.get("main_currency"))
        main = currencies.get(main_id)

        subs: dict[int, WallosSubscription] = {}
        for raw in raw_subs:
            sub = WallosSubscription.from_api(raw, currencies, main, self.convert_currency)
            if sub:
                subs[sub.id] = sub

        return WallosData(
            user=user,
            main_currency=main,
            subscriptions=subs,
            month_cost=month_cost,
            due_soon_days=self.due_soon_days,
        )

    @callback
    def cleanup_devices(self) -> None:
        """Remove devices of subscriptions that no longer exist in Wallos."""
        if not self.data:
            return
        entry_id = self.config_entry.entry_id
        prefix = f"{entry_id}_sub_"
        current = {f"{prefix}{sid}" for sid in self.data.subscriptions}
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(registry, entry_id):
            for domain, ident in device.identifiers:
                if domain == DOMAIN and ident.startswith(prefix) and ident not in current:
                    registry.async_remove_device(device.id)