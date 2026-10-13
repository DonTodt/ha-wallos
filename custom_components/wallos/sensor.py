"""Sensors for Wallos."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WallosConfigEntry, WallosCoordinator
from .entity import WallosEntity, WallosSubscriptionEntity
from .models import WallosData, WallosSubscription, _to_float


@dataclass(frozen=True, kw_only=True)
class WallosSensorDescription(SensorEntityDescription):
    value_fn: Callable[[WallosData, date], Any]
    attrs_fn: Callable[[WallosData, date], dict[str, Any]] | None = None
    monetary: bool = False


def _next_attr(data: WallosData, today: date) -> dict[str, Any]:
    sub = data.next_subscription(today)
    return sub.summary(today) if sub else {}


HUB_SENSORS: tuple[WallosSensorDescription, ...] = (
    WallosSensorDescription(
        key="active_subscriptions",
        translation_key="active_subscriptions",
        icon="mdi:repeat",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d, t: len(d.active),
        attrs_fn=lambda d, t: {"subscriptions": [s.summary(t) for s in d.active]},
    ),
    WallosSensorDescription(
        key="inactive_subscriptions",
        translation_key="inactive_subscriptions",
        icon="mdi:repeat-off",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d, t: len(d.inactive),
        attrs_fn=lambda d, t: {"subscriptions": [s.summary(t) for s in d.inactive]},
    ),
    WallosSensorDescription(
        key="monthly_cost",
        translation_key="monthly_cost",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda d, t: d.monthly_total,
        attrs_fn=lambda d, t: {"by_category": d.by_category},
    ),
    WallosSensorDescription(
        key="yearly_cost",
        translation_key="yearly_cost",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda d, t: d.yearly_total,
    ),
    WallosSensorDescription(
        key="current_month_cost",
        translation_key="current_month_cost",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda d, t: (
            _to_float(d.month_cost.get("monthly_cost")) if d.month_cost else None
        ),
    ),
    WallosSensorDescription(
        key="budget_remaining",
        translation_key="budget_remaining",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda d, t: d.budget_remaining,
        attrs_fn=lambda d, t: {"budget": d.budget, "spent": d.monthly_total},
    ),
    WallosSensorDescription(
        key="next_payment",
        translation_key="next_payment",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d, t: (s.next_payment if (s := d.next_subscription(t)) else None),
        attrs_fn=_next_attr,
    ),
    WallosSensorDescription(
        key="next_payment_subscription",
        translation_key="next_payment_subscription",
        icon="mdi:calendar-arrow-right",
        value_fn=lambda d, t: (s.name if (s := d.next_subscription(t)) else None),
        attrs_fn=_next_attr,
    ),
    WallosSensorDescription(
        key="due_soon",
        translation_key="due_soon",
        icon="mdi:calendar-alert",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d, t: len(d.due_soon(t)),
        attrs_fn=lambda d, t: {
            "days": d.due_soon_days,
            "subscriptions": [s.summary(t) for s in d.due_soon(t)],
        },
    ),
)


@dataclass(frozen=True, kw_only=True)
class WallosSubSensorDescription(SensorEntityDescription):
    value_fn: Callable[[WallosSubscription, date], Any]
    monetary: bool = False


SUB_SENSORS: tuple[WallosSubSensorDescription, ...] = (
    WallosSubSensorDescription(
        key="next_payment",
        translation_key="sub_next_payment",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda s, t: None if s.inactive else s.next_payment,
    ),
    WallosSubSensorDescription(
        key="days_until",
        translation_key="sub_days_until",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s, t: None if s.inactive else s.days_until(t),
    ),
    WallosSubSensorDescription(
        key="price",
        translation_key="sub_price",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda s, t: round(s.price, 2),
    ),
    WallosSubSensorDescription(
        key="monthly_cost",
        translation_key="sub_monthly_cost",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda s, t: round(s.monthly_cost, 2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: WallosConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(WallosSensor(coordinator, d) for d in HUB_SENSORS)

    if not coordinator.per_subscription:
        return

    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new_ids = [sid for sid in coordinator.data.subscriptions if sid not in known]
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            WallosSubscriptionSensor(coordinator, sid, d)
            for sid in new_ids
            for d in SUB_SENSORS
        )

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class WallosSensor(WallosEntity, SensorEntity):
    entity_description: WallosSensorDescription

    def __init__(self, coordinator: WallosCoordinator, description: WallosSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data, dt_util.now().date())

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.monetary:
            return self.coordinator.data.currency_code
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data, dt_util.now().date()) if fn else None


class WallosSubscriptionSensor(WallosSubscriptionEntity, SensorEntity):
    entity_description: WallosSubSensorDescription

    def __init__(
        self, coordinator: WallosCoordinator, sub_id: int, description: WallosSubSensorDescription
    ) -> None:
        super().__init__(coordinator, sub_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sub_{sub_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        sub = self.subscription
        return self.entity_description.value_fn(sub, dt_util.now().date()) if sub else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.monetary and (sub := self.subscription):
            return sub.currency_code
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        sub = self.subscription
        if not sub:
            return None
        return {
            "subscription_id": sub.id,
            "interval": sub.cycle_label,
            "category": sub.category,
            "payer": sub.payer,
            "payment_method": sub.payment_method,
            "auto_renew": sub.auto_renew,
            "inactive": sub.inactive,
            "url": sub.url,
            "notes": sub.notes,
        }
