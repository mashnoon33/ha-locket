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
from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_OTP_CODE,
    CONF_AUTH_METHOD,
    CONF_TOKEN,
    CONF_REFRESH_TOKEN,
    AUTH_METHOD_EMAIL,
    AUTH_METHOD_PHONE,
)

_LOGGER = logging.getLogger(__name__)

STEP_METHOD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_METHOD): vol.In(
            {
                AUTH_METHOD_EMAIL: "Email/Password",
                AUTH_METHOD_PHONE: "Phone OTP",
            }
        ),
    }
)

STEP_EMAIL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): cv.string,
    }
)

STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP_CODE): cv.string,
    }
)


async def validate_email_login(
    hass: HomeAssistant, email: str, password: str
) -> dict[str, Any]:
    """Validate email/password login."""
    api = LocketAPI()

    try:
        login_response = await api.login(email, password)
        await api.close()

        if not login_response.get("idToken"):
            raise InvalidAuth("No token received")

        return {
            "title": email,
            CONF_TOKEN: login_response.get("idToken"),
            CONF_REFRESH_TOKEN: login_response.get("refreshToken"),
        }
    except LocketAPIError as err:
        if (
            err.code == 400
            or "INVALID_PASSWORD" in str(err.message)
            or "EMAIL_NOT_FOUND" in str(err.message)
        ):
            raise InvalidAuth from err
        raise CannotConnect from err
    except Exception as err:
        raise CannotConnect from err
    finally:
        await api.close()


async def validate_phone_otp(
    hass: HomeAssistant, phone: str, otp_code: str
) -> dict[str, Any]:
    """Validate phone OTP login."""
    api = LocketAPI()

    try:
        verify_response = await api.verify_phone_otp(phone, otp_code)
        custom_token = verify_response.get("token")

        if not custom_token:
            raise InvalidAuth("No custom token received")

        exchange_response = await api.exchange_otp_token_for_id_token(custom_token)
        await api.close()

        if not exchange_response.get("idToken"):
            raise InvalidAuth("No ID token received")

        return {
            "title": phone,
            CONF_TOKEN: exchange_response.get("idToken"),
            CONF_REFRESH_TOKEN: exchange_response.get("refreshToken"),
        }
    except LocketAPIError as err:
        if err.code == 400 or "INVALID" in str(err.message):
            raise InvalidAuth from err
        raise CannotConnect from err
    except Exception as err:
        raise CannotConnect from err
    finally:
        await api.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Locket."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth_method: str | None = None
        self._phone: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose authentication method."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_METHOD_DATA_SCHEMA
            )

        self._auth_method = user_input[CONF_AUTH_METHOD]

        if self._auth_method == AUTH_METHOD_EMAIL:
            return await self.async_step_email()
        return await self.async_step_phone()

    async def async_step_email(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle email/password step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="email", data_schema=STEP_EMAIL_DATA_SCHEMA, errors=errors
            )

        try:
            info = await validate_email_login(
                self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            unique_id = user_input[CONF_EMAIL]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_AUTH_METHOD: AUTH_METHOD_EMAIL,
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_TOKEN: info[CONF_TOKEN],
                    CONF_REFRESH_TOKEN: info[CONF_REFRESH_TOKEN],
                },
            )

        return self.async_show_form(
            step_id="email", data_schema=STEP_EMAIL_DATA_SCHEMA, errors=errors
        )

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle phone number step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="phone", data_schema=STEP_PHONE_DATA_SCHEMA, errors=errors
            )

        self._phone = user_input[CONF_PHONE]
        api = LocketAPI()

        try:
            otp_response = await api.request_phone_otp(self._phone)
            await api.close()
            return await self.async_step_otp()
        except LocketAPIError as err:
            await api.close()
            if "INVALID" in str(err.message) or err.code == 400:
                errors["base"] = "invalid_phone"
            else:
                errors["base"] = "cannot_connect"
        except Exception as err:
            await api.close()
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="phone", data_schema=STEP_PHONE_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle OTP verification step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="otp",
                data_schema=STEP_OTP_DATA_SCHEMA,
                errors=errors,
                description_placeholders={"phone": self._phone or ""},
            )

        if not self._phone:
            return self.async_abort(reason="phone_not_set")

        try:
            info = await validate_phone_otp(
                self.hass, self._phone, user_input[CONF_OTP_CODE]
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_otp"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            unique_id = self._phone
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_AUTH_METHOD: AUTH_METHOD_PHONE,
                    CONF_PHONE: self._phone,
                    CONF_TOKEN: info[CONF_TOKEN],
                    CONF_REFRESH_TOKEN: info[CONF_REFRESH_TOKEN],
                },
            )

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"phone": self._phone or ""},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
