"""Constants for the Wallos integration."""
from __future__ import annotations

DOMAIN = "wallos"

CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"  # minutes
CONF_CONVERT_CURRENCY = "convert_currency"
CONF_DUE_SOON_DAYS = "due_soon_days"
CONF_PER_SUBSCRIPTION = "per_subscription_entities"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CONVERT_CURRENCY = True
DEFAULT_DUE_SOON_DAYS = 7
DEFAULT_PER_SUBSCRIPTION = True
