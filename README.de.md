[English](README.md) | **Deutsch**

![Wallos](https://raw.githubusercontent.com/DonTodt/ha-wallos/main/custom_components/wallos/brand/icon.png)
# Wallos – Home Assistant Integration

Bindet deine [Wallos](https://github.com/ellite/Wallos)-Instanz (Abo-Tracker) in Home Assistant ein.

## Installation

**HACS (empfohlen)**

1. In HACS das Menü öffnen → *Benutzerdefinierte Repositories* → `https://github.com/DonTodt/ha-wallos` als Typ *Integration* hinzufügen.
2. **Wallos** herunterladen und Home Assistant neu starten.

**Manuell**

Den Ordner `custom_components/wallos` nach `/config/custom_components/wallos` kopieren und Home Assistant neu starten.

**Einrichtung**

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Wallos**.
2. Wallos-URL (z. B. `http://<DEINE-SERVER-IP>:8282`) und API-Key eintragen (Wallos → Profil → API-Key).

> Der API-Key wird von der Wallos-API als Query-Parameter übertragen – nutze nach Möglichkeit HTTPS.

Benötigt Home Assistant 2025.1 oder neuer (das eigene Icon wird ab 2026.3 angezeigt).

## Optionen (Zahnrad der Integration)

| Option | Standard | Bedeutung |
|---|---|---|
| Update-Intervall | 30 min | Wie oft Wallos abgefragt wird |
| Preise umrechnen | an | Ruft die Abos mit `convert_currency=true` ab → alle Summen in Hauptwährung |
| „Bald fällig“-Schwelle | 7 Tage | Für `Zahlung bald fällig` |
| Entitäten pro Abo | an | Je Abo ein Gerät mit eigenen Entitäten |

## Entitäten

**Gerät „Wallos“**

| Entität | Beschreibung |
|---|---|
| `sensor.wallos_active_subscriptions` | Anzahl aktiver Abos, Attribut `subscriptions` = Liste (Name, Preis, nächste Zahlung, Tage, Kategorie …) |
| `sensor.wallos_inactive_subscriptions` | Anzahl inaktiver/gekündigter Abos |
| `sensor.wallos_monthly_cost` | Normalisierte monatliche Gesamtkosten (Attribut `by_category`) |
| `sensor.wallos_yearly_cost` | Normalisierte Jahreskosten |
| `sensor.wallos_cost_this_month` | Tatsächliche Kosten im aktuellen Monat (`get_monthly_cost`) |
| `sensor.wallos_budget_remaining` | Budget (aus Wallos-Profil) minus monatliche Kosten |
| `sensor.wallos_next_payment` | Datum der nächsten Zahlung |
| `sensor.wallos_next_subscription` | Name des nächsten fälligen Abos |
| `sensor.wallos_payments_due_soon` | Anzahl bald fälliger Zahlungen (Attribut `subscriptions`) |
| `binary_sensor.wallos_payment_due_soon` | An, wenn mind. ein Abo bald fällig ist |
| `calendar.wallos_payments` | Alle Zahlungen als Kalender (zukünftige Wiederholungen werden berechnet) |

**Pro Abo** (eigenes Gerät, Name = Abo-Name)

`Nächste Zahlung` (Datum), `Tage bis zur Zahlung`, `Preis`, `Monatliche Kosten`, `Zahlung bald fällig` (Binary Sensor).

Entity-IDs hängen von deiner HA-Sprache ab – bitte in der UI nachschauen.

## Dashboard-Beispiel

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Abos
    entities:
      - sensor.wallos_active_subscriptions
      - sensor.wallos_monthly_cost
      - sensor.wallos_yearly_cost
      - sensor.wallos_budget_remaining
      - sensor.wallos_next_subscription
      - sensor.wallos_next_payment
  - type: markdown
    title: Alle Abos
    content: >
      {% for s in state_attr('sensor.wallos_active_subscriptions', 'subscriptions') %}
      - **{{ s.name }}** – {{ s.price }} {{ s.currency }} · {{ s.next_payment }} (in {{ s.days_until }} Tagen)
      {% endfor %}
  - type: calendar
    entities:
      - calendar.wallos_payments
```

## Automations-Beispiele

Täglich um 9 Uhr eine Zusammenfassung der bald fälligen Zahlungen:

```yaml
alias: Wallos – Zahlungen bald fällig
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
      title: Abo-Zahlungen
      message: >
        {% for s in state_attr('binary_sensor.wallos_payment_due_soon', 'subscriptions') %}
        {{ s.name }}: {{ s.price }} {{ s.currency }} ({{ s.next_payment }})
        {% endfor %}
```

Einzelnes Abo, 3 Tage vorher:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.netflix_days_until_payment
    below: 4
```

## Hinweise

* Monatskosten werden aus Preis, Zyklus (Tage/Wochen/Monate/Jahre) und Frequenz auf einen Durchschnittsmonat umgerechnet
  (z. B. 60 € alle 2 Monate → 30 €/Monat).
  Summen sind nur sinnvoll, wenn „Preise umrechnen“ aktiv ist (sonst werden unterschiedliche Währungen addiert).
* Wallos verschiebt `next_payment` selbst (Cron). Ist ein Abo ohne Auto-Renew überfällig, wird `days_until` negativ.
* Wird ein Abo in Wallos gelöscht, wird das zugehörige Gerät automatisch entfernt.
