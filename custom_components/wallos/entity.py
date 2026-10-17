"""Base entities for Wallos."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WallosCoordinator
from .models import WallosSubscription


class WallosEntity(CoordinatorEntity[WallosCoordinator]):
    """Entity attached to the Wallos hub device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WallosCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.hub_device_info


class WallosSubscriptionEntity(WallosEntity):
    """Entity attached to a per-subscription device."""

    def __init__(self, coordinator: WallosCoordinator, sub_id: int) -> None:
        super().__init__(coordinator)
        self._sub_id = sub_id
        sub = coordinator.data.subscriptions[sub_id]
        entry_id = coordinator.config_entry.entry_id
        # Create the device up front so it can reference the hub via `via_device_id`
        # (the `via_device` key in DeviceInfo is deprecated since HA 2026.8).
        coordinator.ensure_subscription_device(sub)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_sub_{sub_id}")},
        )

    @property
    def subscription(self) -> WallosSubscription | None:
        return self.coordinator.data.subscriptions.get(self._sub_id)

    @property
    def available(self) -> bool:
        return super().available and self.subscription is not None