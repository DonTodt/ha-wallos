"""Data models for Wallos."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

DAYS_PER_MONTH = 30.4375
CYCLE_UNITS = {1: "day", 2: "week", 3: "month", 4: "year"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _monthly_factor(cycle: int, frequency: int) -> float:
    """How many payments (fraction) fall into an average month."""
    freq = max(frequency, 1)
    if cycle == 1:  # days
        return DAYS_PER_MONTH / freq
    if cycle == 2:  # weeks
        return (DAYS_PER_MONTH / 7) / freq
    if cycle == 4:  # years
        return 1 / (12 * freq)
    return 1 / freq  # months


@dataclass(frozen=True)
class WallosCurrency:
    id: int
    code: str
    symbol: str
    name: str
    rate: float


@dataclass(frozen=True)
class WallosSubscription:
    id: int
    name: str
    price: float
    currency_code: str | None
    currency_symbol: str | None
    cycle: int
    frequency: int
    next_payment: date | None
    start_date: date | None
    auto_renew: bool
    inactive: bool
    notify: bool
    notify_days_before: int | None
    category: str | None
    payer: str | None
    payment_method: str | None
    url: str | None
    notes: str | None
    logo: str | None

    @classmethod
    def from_api(
        cls,
        raw: dict[str, Any],
        currencies: dict[int, WallosCurrency],
        main: WallosCurrency | None,
        converted: bool,
    ) -> WallosSubscription | None:
        sid = _to_int(raw.get("id"))
        if sid is None:
            return None
        if converted and main:
            currency = main
        else:
            currency = currencies.get(_to_int(raw.get("currency_id")), main)
        return cls(
            id=sid,
            name=str(raw.get("name") or f"Subscription {sid}"),
            price=_to_float(raw.get("price")),
            currency_code=currency.code if currency else None,
            currency_symbol=currency.symbol if currency else None,
            cycle=_to_int(raw.get("cycle"), 3) or 3,
            frequency=_to_int(raw.get("frequency"), 1) or 1,
            next_payment=_to_date(raw.get("next_payment")),
            start_date=_to_date(raw.get("start_date")),
            auto_renew=_to_bool(raw.get("auto_renew")),
            inactive=_to_bool(raw.get("inactive")),
            notify=_to_bool(raw.get("notify")),
            notify_days_before=_to_int(raw.get("notify_days_before")),
            category=raw.get("category_name") or None,
            payer=raw.get("payer_user_name") or None,
            payment_method=raw.get("payment_method_name") or None,
            url=raw.get("url") or None,
            notes=raw.get("notes") or None,
            logo=raw.get("logo") or None,
        )

    @property
    def monthly_cost(self) -> float:
        return self.price * _monthly_factor(self.cycle, self.frequency)

    @property
    def yearly_cost(self) -> float:
        return self.monthly_cost * 12

    @property
    def cycle_label(self) -> str:
        return f"{self.frequency} {CYCLE_UNITS.get(self.cycle, 'month')}(s)"

    def days_until(self, today: date) -> int | None:
        if self.next_payment is None:
            return None
        return (self.next_payment - today).days

    def occurrences(self, start: date, end: date) -> Iterator[date]:
        """Projected payment dates between start and end (inclusive)."""
        if self.next_payment is None or self.inactive:
            return
        freq = max(self.frequency, 1)
        for k in range(2000):
            if self.cycle == 1:
                d = self.next_payment + timedelta(days=freq * k)
            elif self.cycle == 2:
                d = self.next_payment + timedelta(weeks=freq * k)
            elif self.cycle == 3:
                d = self.next_payment + relativedelta(months=freq * k)
            elif self.cycle == 4:
                d = self.next_payment + relativedelta(years=freq * k)
            else:
                return
            if d > end:
                return
            if d >= start:
                yield d

    def summary(self, today: date) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "price": round(self.price, 2),
            "currency": self.currency_symbol or self.currency_code,
            "monthly_cost": round(self.monthly_cost, 2),
            "interval": self.cycle_label,
            "next_payment": self.next_payment.isoformat() if self.next_payment else None,
            "days_until": self.days_until(today),
            "category": self.category,
            "payer": self.payer,
            "payment_method": self.payment_method,
            "auto_renew": self.auto_renew,
        }


@dataclass
class WallosData:
    """Everything fetched from Wallos in one refresh."""

    user: dict[str, Any]
    main_currency: WallosCurrency | None
    subscriptions: dict[int, WallosSubscription]
    month_cost: dict[str, Any] | None
    due_soon_days: int
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def currency_code(self) -> str | None:
        return self.main_currency.code if self.main_currency else None

    @property
    def currency_symbol(self) -> str | None:
        return self.main_currency.symbol if self.main_currency else None

    @property
    def active(self) -> list[WallosSubscription]:
        subs = [s for s in self.subscriptions.values() if not s.inactive]
        return sorted(subs, key=lambda s: (s.next_payment or date.max, s.name.lower()))

    @property
    def inactive(self) -> list[WallosSubscription]:
        return [s for s in self.subscriptions.values() if s.inactive]

    @property
    def monthly_total(self) -> float:
        return round(sum(s.monthly_cost for s in self.active), 2)

    @property
    def yearly_total(self) -> float:
        return round(sum(s.yearly_cost for s in self.active), 2)

    @property
    def by_category(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for s in self.active:
            key = s.category or "-"
            result[key] = round(result.get(key, 0) + s.monthly_cost, 2)
        return result

    @property
    def budget(self) -> float | None:
        value = _to_float(self.user.get("budget"), 0.0)
        return value if value > 0 else None

    @property
    def budget_remaining(self) -> float | None:
        if self.budget is None:
            return None
        return round(self.budget - self.monthly_total, 2)

    def next_subscription(self, today: date) -> WallosSubscription | None:
        upcoming = [s for s in self.active if s.next_payment and s.next_payment >= today]
        return upcoming[0] if upcoming else None

    def due_soon(self, today: date) -> list[WallosSubscription]:
        result = []
        for s in self.active:
            days = s.days_until(today)
            if days is not None and 0 <= days <= self.due_soon_days:
                result.append(s)
        return result
