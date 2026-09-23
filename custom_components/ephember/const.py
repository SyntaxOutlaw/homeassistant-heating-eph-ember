"""Shared constants for the EPH Controls integration."""

from datetime import timedelta

DOMAIN = "ephember"
MANUFACTURER = "EPH Controls"

CONF_API_VERSION = "api_version"
API_VERSION_AUTO = "auto"
API_VERSION_LEGACY = "legacy"
API_VERSION_CURRENT = "current"

DEFAULT_API_VERSION = API_VERSION_AUTO
SCAN_INTERVAL = timedelta(seconds=60)

ATTR_BOOST_ACTIVE = "boost_active"
ATTR_BOOST_FINISH = "boost_finish"
ATTR_BOOST_HOURS = "boost_hours"
ATTR_IS_ONLINE = "is_online"
ATTR_ZONE_ID = "zone_id"
ATTR_GATEWAY_ID = "gateway_id"
ATTR_PREFIX = "prefix"
ATTR_TEMPERATURE_AVAILABLE = "temperature_available"

PRESET_ALL_DAY = "all_day"

SERVICE_BOOST_ZONE = "boost_zone"
SERVICE_CANCEL_BOOST = "cancel_boost"

TEMP_SENTINEL = -300.0
MIN_TEMP = 5.0
MAX_TEMP = 35.0
TEMP_STEP = 0.5
DEFAULT_BOOST_HOURS = 1
DEFAULT_BOOST_TEMP = 21.0
DEFAULT_HOT_WATER_BOOST_TEMP = 60.0
