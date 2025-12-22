"""Data update coordinator for Locket."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LocketAPI, LocketAPIError
from .const import CONF_TOKEN, CONF_REFRESH_TOKEN, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LocketDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Locket data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = LocketAPI(token=entry.data.get(CONF_TOKEN))
        self.entry = entry
        self._refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

        super().__init__(
            hass,
            _LOGGER,
            name="Locket",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Locket API."""
        try:
            moment = await self.api.fetch_latest_moment()
            return {
                "moment": moment,
                "latest_image_url": (
                    moment.get("data", [{}])[0].get("thumbnail_url")
                    if moment.get("data")
                    else None
                ),
                "missed_moments": moment.get("missed_moments_count", 0),
            }
        except LocketAPIError as err:
            if err.code == 401:
                _LOGGER.warning("Token expired, attempting to refresh")
                try:
                    refresh_response = await self.api.refresh_token(self._refresh_token)
                    new_token = refresh_response.get("id_token")
                    new_refresh_token = refresh_response.get("refresh_token")
                    
                    if new_token:
                        self.api.set_token(new_token)
                        self.hass.config_entries.async_update_entry(
                            self.entry,
                            data={
                                **self.entry.data,
                                CONF_TOKEN: new_token,
                                CONF_REFRESH_TOKEN: new_refresh_token or self._refresh_token,
                            },
                        )
                        self._refresh_token = new_refresh_token or self._refresh_token
                        
                        moment = await self.api.fetch_latest_moment()
                        return {
                            "moment": moment,
                            "latest_image_url": (
                                moment.get("data", [{}])[0].get("thumbnail_url")
                                if moment.get("data")
                                else None
                            ),
                            "missed_moments": moment.get("missed_moments_count", 0),
                        }
                except Exception as refresh_err:
                    _LOGGER.error("Failed to refresh token: %s", refresh_err)
            
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_unload(self) -> None:
        """Unload the coordinator."""
        await self.api.close()

