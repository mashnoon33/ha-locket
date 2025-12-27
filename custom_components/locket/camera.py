"""Camera platform for Locket."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LocketDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Locket camera from a config entry."""
    coordinator: LocketDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([LocketCamera(coordinator)])


class LocketCamera(CoordinatorEntity, Camera):
    """Representation of a Locket moment camera."""

    def __init__(self, coordinator: LocketDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_moment"
        self._last_image_url: str | None = None
        self._attr_should_poll = False
        _LOGGER.debug("Initialized LocketCamera with unique_id: %s", self._attr_unique_id)

    @property
    def name(self) -> str:
        """Return the name of the camera."""
        if not self.coordinator.data:
            return "Locket Moment"
        
        moment = self.coordinator.data.get("moment", {})
        moment_data = moment.get("data", [{}])[0] if moment.get("data") else {}
        caption = moment_data.get("caption", "")
        
        if caption:
            return f"Locket Moment: {caption}"
        return "Locket Moment"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("LocketCamera added to Home Assistant")
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            _LOGGER.warning("Coordinator data is None, skipping update")
            return

        new_image_url = self.coordinator.data.get("latest_image_url")
        moment = self.coordinator.data.get("moment", {})
        moment_data = moment.get("data", [{}])[0] if moment.get("data") else {}
        caption = moment_data.get("caption", "")
        
        if new_image_url != self._last_image_url:
            _LOGGER.info(
                "New moment detected. Image URL changed from %s to %s, Caption: %s",
                self._last_image_url,
                new_image_url,
                caption or "(no caption)"
            )
            self._last_image_url = new_image_url
            self.async_write_ha_state()
        else:
            _LOGGER.debug("Coordinator updated but image URL unchanged: %s", new_image_url)
            self.async_write_ha_state()

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if not self.coordinator.data:
            _LOGGER.warning("No coordinator data available for image fetch")
            return None

        image_url = self.coordinator.data.get("latest_image_url")
        if not image_url:
            _LOGGER.warning("No image URL available in coordinator data")
            return None

        _LOGGER.debug("Fetching image from URL: %s", image_url)
        
        try:
            session = await self.coordinator.api._get_session()
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    _LOGGER.debug("Successfully fetched image, size: %d bytes", len(image_data))
                    return image_data
                else:
                    _LOGGER.warning("Failed to fetch image, status code: %d", response.status)
        except Exception as err:
            _LOGGER.error("Error fetching image from %s: %s", image_url, err, exc_info=True)
            return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the camera state attributes."""
        if not self.coordinator.data:
            return {}

        moment = self.coordinator.data.get("moment", {})
        moment_data = moment.get("data", [{}])[0] if moment.get("data") else {}

        attrs = {
            "missed_moments": self.coordinator.data.get("missed_moments", 0),
        }

        if moment_data:
            attrs.update({
                "caption": moment_data.get("caption", ""),
                "canonical_uid": moment_data.get("canonical_uid", ""),
                "user": moment_data.get("user", ""),
            })

            if moment_data.get("date"):
                date_obj = moment_data["date"]
                if isinstance(date_obj, dict) and "_seconds" in date_obj:
                    from datetime import datetime
                    attrs["moment_date"] = datetime.fromtimestamp(
                        date_obj["_seconds"]
                    ).isoformat()

        return attrs

