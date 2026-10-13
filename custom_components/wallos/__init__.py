"""The Wallos integration."""
from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import WallosApiClient
from .const import CONF_VERIFY_SSL
from .coordinator import WallosConfigEntry, WallosCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: WallosConfigEntry) -> bool:
    client = WallosApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_VERIFY_SSL, True),
    )
    coordinator = WallosCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove devices of subscriptions deleted in Wallos.
    coordinator.cleanup_devices()
    entry.async_on_unload(coordinator.async_add_listener(coordinator.cleanup_devices))

    # "days until" values change at midnight, even without a new API refresh.
    @callback
    def _midnight(_now) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(async_track_time_change(hass, _midnight, hour=0, minute=0, second=10))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: WallosConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WallosConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
