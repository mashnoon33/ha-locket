"""Config flow for Locket integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import LocketAPI, LocketAPIError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = LocketAPI()

    try:
        login_response = await api.login(data[CONF_EMAIL], data[CONF_PASSWORD])
        await api.close()

        if not login_response.get("idToken"):
            raise InvalidAuth("No token received")

        return {
            "title": data[CONF_EMAIL],
            CONF_TOKEN: login_response.get("idToken"),
            CONF_REFRESH_TOKEN: login_response.get("refreshToken"),
        }
    except LocketAPIError as err:
        if err.code == 400 or "INVALID_PASSWORD" in str(err.message) or "EMAIL_NOT_FOUND" in str(err.message):
            raise InvalidAuth from err
        raise CannotConnect from err
    except Exception as err:
        raise CannotConnect from err
    finally:
        await api.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Locket."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data={
                CONF_EMAIL: user_input[CONF_EMAIL],
                CONF_TOKEN: info[CONF_TOKEN],
                CONF_REFRESH_TOKEN: info[CONF_REFRESH_TOKEN],
            })

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

