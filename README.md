**English** | [Deutsch](README.de.md)

![Wallos](https://raw.githubusercontent.com/DonTodt/ha-wallos/main/custom_components/wallos/brand/icon.png)
# Wallos – Home Assistant Integration

Integrates your [Wallos](https://github.com/ellite/Wallos) instance (subscription tracker) into Home Assistant.

## Installation

**HACS (recommended)**

1. In HACS, open the menu → *Custom repositories* → add `https://github.com/DonTodt/ha-wallos` as type *Integration*.
2. Download **Wallos** and restart Home Assistant.

**Manual**

Copy the folder `custom_components/wallos` to `/config/custom_components/wallos` and restart Home Assistant.

**Setup**

1. Go to **Settings → Devices & services → Add integration → Wallos**.
2. Enter your Wallos URL (e.g. `http://<YOUR-SERVER-IP>:8282`) and your API key (Wallos → Profile → API key).

> The Wallos API transmits the API key as a query parameter – use HTTPS whenever possible.

Requires Home Assistant 2025.1 or newer (custom brand icons are shown from 2026.3).

## Options (gear icon of the integration)

| Option | Default | Meaning |
|---|---|---|
| Update interval | 30 min | How often Wallos is polled |
| Convert prices | on | Fetches subscriptions with `convert_currency=true` → all totals in your main currency |
| "Due soon" threshold | 7 days | Used by `Payment due soon` |
| Entities per subscription | on | Creates a device with its own entities for each subscription |

## Entities

**Device "Wallos"**

| Entity | Description |
|---|---|
| `sensor.wallos_active_subscriptions` | Number of active subscriptions; attribute `subscriptions` = list (name, price, next payment, days, category …) |
| `sensor.wallos_inactive_subscriptions` | Number of inactive/cancelled subscriptions |
| `sensor.wallos_monthly_cost` | Normalized total monthly cost (attribute `by_category`) |
| `sensor.wallos_yearly_cost` | Normalized yearly cost |
| `sensor.wallos_cost_this_month` | Actual cost for the current month (`get_monthly_cost`) |
| `sensor.wallos_budget_remaining` | Budget (from your Wallos profile) minus monthly cost |
| `sensor.wallos_next_payment` | Date of the next payment |
| `sensor.wallos_next_subscription` | Name of the next subscription due |
| `sensor.wallos_payments_due_soon` | Number of payments due soon (attribute `subscriptions`) |
| `binary_sensor.wallos_payment_due_soon` | On if at least one subscription is due soon |
| `calendar.wallos_payments` | All payments as a calendar (future recurrences are projected) |

**Per subscription** (own device, named after the subscription)

`Next payment` (date), `Days until payment`, `Price`, `Monthly cost`, `Payment due soon` (binary).

Entity IDs depend on your Home Assistant language – please check them in the UI.

## Dashboard example

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Subscriptions
    entities:
      - sensor.wallos_active_subscriptions
      - sensor.wallos_monthly_cost
      - sensor.wallos_yearly_cost
      - sensor.wallos_budget_remaining
      - sensor.wallos_next_subscription
      - sensor.wallos_next_payment
  - type: markdown
    title: All subscriptions
    content: >
      {% for s in state_attr('sensor.wallos_active_subscriptions', 'subscriptions') %}
      - **{{ s.name }}** – {{ s.price }} {{ s.currency }} · {{ s.next_payment }} (in {{ s.days_until }} days)
      {% endfor %}
  - type: calendar
    entities:
      - calendar.wallos_payments
```

## Automation examples

Daily summary at 9:00 of payments that are due soon:

```yaml
alias: Wallos – payments due soon
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: state
    entity_id: binary_sensor.wallos_payment_due_soon
    state: "on"
actions:
  - action: notify.notify
    data:
      title: Subscription payments
      message: >
        {% for s in state_attr('binary_sensor.wallos_payment_due_soon', 'subscriptions') %}
        {{ s.name }}: {{ s.price }} {{ s.currency }} ({{ s.next_payment }})
        {% endfor %}
```

A single subscription, 3 days before payment:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.netflix_days_until_payment
    below: 4
```

## Notes

* Monthly cost is normalized to an average month from price, cycle (days/weeks/months/years) and frequency
  (e.g. 60 € every 2 months → 30 €/month).
  Totals are only meaningful if "Convert prices" is enabled (otherwise different currencies are added up).
* Wallos advances `next_payment` itself (cron). If a subscription without auto-renew is overdue, `days_until` becomes negative.
* If a subscription is deleted in Wallos, its device is removed automatically.
