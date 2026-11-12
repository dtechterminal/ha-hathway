"""Sign in with the registered mobile number and an SMS OTP, like the Hathway app."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (ConfigEntry, ConfigFlow, ConfigFlowResult,
                                          OptionsFlow)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (NumberSelector, NumberSelectorConfig,
                                            NumberSelectorMode, SelectSelector,
                                            SelectSelectorConfig)

from .api import HathwayAuthError, HathwayClient, HathwayError, OtpChallenge
from .const import (CONF_ACCOUNT_NO, CONF_MOBILE, CONF_OTP, CONF_RESET_DAY,
                    CONF_SCAN_MINUTES, CONF_TOKEN, DEFAULT_RESET_DAY, DEFAULT_SCAN_MINUTES,
                    DOMAIN, MAX_SCAN_MINUTES, MIN_SCAN_MINUTES)

_LOGGER = logging.getLogger(__name__)
MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def _clean_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) > 10 and digits.startswith("91") else digits


class HathwayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._client: HathwayClient | None = None
        self._challenge: OtpChallenge | None = None

    def _new_client(self) -> HathwayClient:
        return HathwayClient(async_get_clientsession(self.hass))

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["otp", "token"])

    async def _request_otp(self, mobile: str) -> str | None:
        """Send the SMS; return an error key or None."""
        self._client = self._new_client()
        try:
            self._challenge = await self._client.request_otp(mobile)
        except HathwayAuthError:
            return "no_account"
        except HathwayError as err:
            _LOGGER.warning("OTP request failed: %s", err)
            return "cannot_connect"
        return None

    async def async_step_otp(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            mobile = _clean_mobile(user_input[CONF_MOBILE])
            if not MOBILE_RE.match(mobile):
                errors[CONF_MOBILE] = "invalid_mobile"
            elif not (error := await self._request_otp(mobile)):
                return await self.async_step_verify()
            else:
                errors["base"] = error
        return self.async_show_form(
            step_id="otp", errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_MOBILE): str}))

    async def async_step_verify(self, user_input=None) -> ConfigFlowResult:
        assert self._client and self._challenge
        accounts = self._challenge.accounts
        errors: dict[str, str] = {}
        if user_input is not None:
            account_no = user_input.get(CONF_ACCOUNT_NO, accounts[0])
            try:
                token = await self._client.login(
                    self._challenge, user_input[CONF_OTP].strip(), account_no)
            except HathwayAuthError:
                errors["base"] = "invalid_otp"
            except HathwayError as err:
                _LOGGER.warning("Login failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(self._challenge.mobile, account_no, token)
        schema: dict[Any, Any] = {vol.Required(CONF_OTP): str}
        if len(accounts) > 1:
            schema[vol.Required(CONF_ACCOUNT_NO, default=accounts[0])] = SelectSelector(
                SelectSelectorConfig(options=accounts))
        return self.async_show_form(
            step_id="verify", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={"mobile": "******" + self._challenge.mobile[-4:]})

    async def async_step_token(self, user_input=None) -> ConfigFlowResult:
        """Use a session token taken from an existing install (no SMS needed)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mobile = _clean_mobile(user_input[CONF_MOBILE])
            client = HathwayClient(async_get_clientsession(self.hass), mobile=mobile,
                                   account_no=user_input[CONF_ACCOUNT_NO].strip(),
                                   token=user_input[CONF_TOKEN].strip())
            try:
                await client.account_status()
            except HathwayAuthError:
                errors["base"] = "invalid_auth"
            except HathwayError as err:
                _LOGGER.warning("Token check failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(mobile, client.account_no, client.token)
        return self.async_show_form(step_id="token", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_MOBILE): str,
            vol.Required(CONF_ACCOUNT_NO): str,
            vol.Required(CONF_TOKEN): str,
        }))

    async def _finish(self, mobile: str, account_no: str, token: str) -> ConfigFlowResult:
        data = {CONF_MOBILE: mobile, CONF_ACCOUNT_NO: account_no, CONF_TOKEN: token}
        await self.async_set_unique_id(account_no)
        if self.source == "reauth":
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(title=f"Hathway {account_no}", data=data)

    # --- re-authentication -----------------------------------------------
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        mobile = entry.data[CONF_MOBILE]
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._request_otp(mobile)):
                return await self.async_step_verify()
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", errors=errors,
            description_placeholders={"mobile": "******" + mobile[-4:]})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HathwayOptionsFlow()


class HathwayOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={
                CONF_RESET_DAY: int(user_input[CONF_RESET_DAY]),
                CONF_SCAN_MINUTES: int(user_input[CONF_SCAN_MINUTES]),
            })
        options = self.config_entry.options
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_RESET_DAY,
                         default=options.get(CONF_RESET_DAY, DEFAULT_RESET_DAY)):
                NumberSelector(NumberSelectorConfig(min=1, max=31, step=1,
                                                    mode=NumberSelectorMode.BOX)),
            vol.Required(CONF_SCAN_MINUTES,
                         default=options.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)):
                NumberSelector(NumberSelectorConfig(
                    min=MIN_SCAN_MINUTES, max=MAX_SCAN_MINUTES, step=5,
                    unit_of_measurement="min", mode=NumberSelectorMode.BOX)),
        }))
