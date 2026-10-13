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
        url = sub.url if sub.url and sub.url.startswith(("http://", "https://")) else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_sub_{sub_id}")},
            name=sub.name,
            manufacturer="Wallos",
            model=sub.category or "Subscription",
            via_device=(DOMAIN, entry_id),
            configuration_url=url,
        )

    @property
    def subscription(self) -> WallosSubscription | None:
        return self.coordinator.data.subscriptions.get(self._sub_id)

    @property
    def available(self) -> bool:
        return super().available and self.subscription is not None
