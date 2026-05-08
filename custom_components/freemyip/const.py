"""Constants for FreeMyIP."""

from __future__ import annotations

from typing import Final

CONF_API_ECONOMY: Final = "api_key_economy"
CONF_ENABLE_IPV6: Final = "enable_ipv6"

DOMAIN: Final = "freemyip"
SHORT_NAME: Final = "FreeMyIP"
DEFAULT_INTERVAL: Final = 23

TIMEOUT: Final = 10
RETRY_ATTEMPTS: Final = 3
RETRY_DELAY: Final = 2
UPDATE_URL: Final = "https://freemyip.com/update"

CHECKIP_V4_URL: Final = "https://freemyip.com/checkip"
CHECKIP_V6_URL: Final = "https://api6.ipify.org"

SERVICE_REFRESH: Final = "refresh"
