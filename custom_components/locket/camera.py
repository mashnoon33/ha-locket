"""Camera platform for Locket."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


class LocketCamera(Camera):
    """Representation of a Locket moment camera."""

    _attr_name = "Locket Moment"

    def __init__(self, coordinator: LocketDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_moment"

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if not self.coordinator.data or not self.coordinator.data.get("latest_image_url"):
            return None

        image_url = self.coordinator.data["latest_image_url"]
        
        try:
            session = await self.coordinator.api._get_session()
            async with session.get(image_url) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as err:
            _LOGGER.error("Error fetching image: %s", err)
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

