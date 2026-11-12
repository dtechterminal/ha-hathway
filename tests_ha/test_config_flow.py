from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hathway.api import HathwayAuthError, HathwayError
from custom_components.hathway.const import CONF_RESET_DAY, CONF_SCAN_MINUTES, DOMAIN

from .conftest import DATA


async def _start(hass, option):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result["flow_id"],
                                                          {"next_step_id": option})


async def test_otp_flow(hass, api):
    result = await _start(hass, "otp")
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
                                                            {"mobile": "12345"})
    assert result["errors"] == {"mobile": "invalid_mobile"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
                                                            {"mobile": "+91 90000 00001"})
    assert result["step_id"] == "verify"
    api["otp"].assert_awaited_once_with("9000000001")

    api["login"].side_effect = HathwayAuthError("bad otp")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "000000"})
    assert result["errors"] == {"base": "invalid_otp"}

    api["login"].side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "123456"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1000000001"
    assert result["data"] == {"mobile": "9000000001", "account_no": "1000000001",
                              "token": "n" * 40}


async def test_otp_request_fails(hass, api):
    api["otp"].side_effect = HathwayError("down")
    result = await _start(hass, "otp")
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
                                                            {"mobile": "9000000001"})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_token_flow(hass, api):
    result = await _start(hass, "token")
    api["status"].side_effect = HathwayAuthError("nope")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["errors"] == {"base": "invalid_auth"}
    api["status"].side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA


async def test_duplicate_aborts(hass, api, entry):
    result = await _start(hass, "token")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass, api, entry, ist):
    await hass.config_entries.async_setup(entry.entry_id)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "verify"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "123456"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == "n" * 40


async def test_options(hass, api, entry, ist):
    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_RESET_DAY: 1, CONF_SCAN_MINUTES: 120})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_RESET_DAY: 1, CONF_SCAN_MINUTES: 120}
