"""Shared station metadata for Hangzhou forecast and ML pipelines."""

HANGZHOU_STATION_ID = "58457"
HANGZHOU_STATION_NAME = "杭州国家站 / 馒头山"
HANGZHOU_OBS_FALLBACK_NAME = "Meteostat 58457"
HANGZHOU_LAT = 30.2444
HANGZHOU_LON = 120.1528
HANGZHOU_TIMEZONE = "Asia/Shanghai"


def get_hangzhou_station_metadata() -> dict:
    """Return a JSON-serializable snapshot of the configured target station."""
    return {
        "station_id": HANGZHOU_STATION_ID,
        "station_name": HANGZHOU_STATION_NAME,
        "latitude": HANGZHOU_LAT,
        "longitude": HANGZHOU_LON,
        "timezone": HANGZHOU_TIMEZONE,
    }
