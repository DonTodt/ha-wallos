"""Calendar of upcoming Wallos payments."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WallosConfigEntry, WallosCoordinator
from .entity import WallosEntity
from .models import WallosSubscription


async def async_setup_entry(
    hass: HomeAssistant, entry: WallosConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([WallosCalendar(entry.runtime_data)])


def _event(sub: WallosSubscription, day: date) -> CalendarEvent:
    symbol = sub.currency_symbol or sub.currency_code or ""
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=f"{sub.name}: {sub.price:.2f} {symbol}".strip(),
        description="\n".join(
            filter(None, [sub.cycle_label, sub.category, sub.payment_method, sub.notes])
        ),
    )


class WallosCalendar(WallosEntity, CalendarEntity):
    _attr_translation_key = "payments"

    def __init__(self, coordinator: WallosCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        sub = self.coordinator.data.next_subscription(dt_util.now().date())
        if sub and sub.next_payment:
            return _event(sub, sub.next_payment)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = start_date.date()
        end = (end_date - timedelta(microseconds=1)).date()
        events: list[CalendarEvent] = []
        for sub in self.coordinator.data.active:
            events.extend(_event(sub, d) for d in sub.occurrences(start, end))
        return sorted(events, key=lambda e: e.start)
