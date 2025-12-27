"""Data update coordinator for Locket."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LocketAPI, LocketAPIError
from .const import (
    CONF_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class LocketDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Locket data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = LocketAPI(token=entry.data.get(CONF_TOKEN))
        self.entry = entry
        self._refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        _LOGGER.info("Initializing coordinator with update interval: %d seconds", update_interval)

        super().__init__(
            hass,
            _LOGGER,
            name="Locket",
            update_interval=timedelta(seconds=update_interval),
        )

        entry.async_on_unload(
            entry.add_update_listener(self._async_update_listener)
        )

    async def _async_update_listener(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        new_interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        current_interval = self.update_interval.total_seconds() if self.update_interval else DEFAULT_UPDATE_INTERVAL
        
        if new_interval != current_interval:
            _LOGGER.info(
                "Update interval changed from %d to %d seconds",
                int(current_interval),
                new_interval
            )
            self.update_interval = timedelta(seconds=new_interval)

    async def _async_update_data(self) -> dict:
        """Fetch data from Locket API."""
        _LOGGER.debug("Starting data update from Locket API")
        try:
            moment = await self.api.fetch_latest_moment()
            
            image_url = (
                moment.get("data", [{}])[0].get("thumbnail_url")
                if moment.get("data")
                else None
            )
            missed_moments = moment.get("missed_moments_count", 0)
            
            _LOGGER.info(
                "Successfully fetched moment data. Image URL: %s, Missed moments: %d",
                image_url,
                missed_moments
            )
            
            return {
                "moment": moment,
                "latest_image_url": image_url,
                "missed_moments": missed_moments,
            }
        except LocketAPIError as err:
            if err.code == 401:
                _LOGGER.warning("Token expired (401), attempting to refresh")
                try:
                    refresh_response = await self.api.refresh_token(self._refresh_token)
                    new_token = refresh_response.get("id_token")
                    new_refresh_token = refresh_response.get("refresh_token")
                    
                    if new_token:
                        _LOGGER.info("Token refresh successful, retrying moment fetch")
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
                        image_url = (
                            moment.get("data", [{}])[0].get("thumbnail_url")
                            if moment.get("data")
                            else None
                        )
                        missed_moments = moment.get("missed_moments_count", 0)
                        
                        _LOGGER.info(
                            "Successfully fetched moment after token refresh. Image URL: %s, Missed moments: %d",
                            image_url,
                            missed_moments
                        )
                        
                        return {
                            "moment": moment,
                            "latest_image_url": image_url,
                            "missed_moments": missed_moments,
                        }
                    else:
                        _LOGGER.error("Token refresh returned no new token")
                except Exception as refresh_err:
                    _LOGGER.error("Failed to refresh token: %s", refresh_err, exc_info=True)
            else:
                _LOGGER.error("Locket API error: %s (code: %s)", err.message, err.code)
            
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during data update: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_unload(self) -> None:
        """Unload the coordinator."""
        await self.api.close()

