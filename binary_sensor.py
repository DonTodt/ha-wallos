"""Binary sensors for Wallos."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WallosConfigEntry, WallosCoordinator
from .entity import WallosEntity, WallosSubscriptionEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: WallosConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([WallosDueSoonBinarySensor(coordinator)])

    if not coordinator.per_subscription:
        return

    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new_ids = [sid for sid in coordinator.data.subscriptions if sid not in known]
        if new_ids:
            known.update(new_ids)
            async_add_entities(WallosSubDueSoonBinarySensor(coordinator, sid) for sid in new_ids)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class WallosDueSoonBinarySensor(WallosEntity, BinarySensorEntity):
    """On if at least one payment is due within the configured number of days."""

    _attr_translation_key = "payment_due_soon"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: WallosCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_payment_due_soon"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.due_soon(dt_util.now().date()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        data = self.coordinator.data
        return {
            "days": data.due_soon_days,
            "subscriptions": [s.summary(today) for s in data.due_soon(today)],
        }


class WallosSubDueSoonBinarySensor(WallosSubscriptionEntity, BinarySensorEntity):
    _attr_translation_key = "sub_due_soon"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: WallosCoordinator, sub_id: int) -> None:
        super().__init__(coordinator, sub_id)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sub_{sub_id}_due_soon"

    @property
    def is_on(self) -> bool | None:
        sub = self.subscription
        if not sub or sub.inactive:
            return False
        days = sub.days_until(dt_util.now().date())
        return days is not None and 0 <= days <= self.coordinator.data.due_soon_days
