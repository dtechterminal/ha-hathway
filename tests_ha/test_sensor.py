from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState, SOURCE_REAUTH
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hathway.api import HathwayAuthError
from custom_components.hathway.const import CONF_RESET_DAY


async def _setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(hass, api, entry, ist, freezer):
    freezer.move_to("2026-11-12 06:30:00+00:00")  # 12:00 IST
    await _setup(hass, entry)
    used = hass.states.get("sensor.hathway_data_used")
    assert used.attributes["unit_of_measurement"] == "GiB"
    assert abs(float(used.state) - 2562822 / 1024) < 0.01
    assert used.attributes["cycle_start"] == "2026-10-26"
    assert hass.states.get("sensor.hathway_usage_percentage").state == "71.5"
    assert hass.states.get("sensor.hathway_days_until_reset").state == "14"
    assert hass.states.get("sensor.hathway_cycle_start").state == "2026-10-26"
    assert hass.states.get("sensor.hathway_next_reset").state == "2026-11-26"
    assert hass.states.get("sensor.hathway_expiry_date").state == "2027-10-25"
    remaining = float(hass.states.get("sensor.hathway_data_remaining").state)
    assert abs(remaining - 1022202 / 1024) < 0.01
    projected = hass.states.get("sensor.hathway_projected_usage")
    assert abs(float(projected.state) - 2562822 / 1024 / 17.5 * 31) < 0.5
    latest = hass.states.get("sensor.hathway_latest_day_usage")
    assert latest.attributes["date"] == "2026-11-12"
    assert hass.states.get("sensor.hathway_fup_status").state == "Within Limit"


async def test_midnight_rollover(hass, api, entry, ist, freezer):
    freezer.move_to("2026-11-25 18:00:00+00:00")  # 23:30 IST, day before reset
    await _setup(hass, entry)
    assert hass.states.get("sensor.hathway_days_until_reset").state == "1"
    freezer.move_to("2026-11-25 18:30:10+00:00")  # 00:00:10 IST on the 26th
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.hathway_cycle_start").state == "2026-11-26"
    assert hass.states.get("sensor.hathway_days_until_reset").state == "30"
    assert hass.states.get("sensor.hathway_projected_usage").state == "unknown"


async def test_reset_day_option(hass, api, entry, ist, freezer):
    freezer.move_to("2026-11-12 06:30:00+00:00")
    hass.config_entries.async_update_entry(entry, options={CONF_RESET_DAY: 1})
    await _setup(hass, entry)
    assert hass.states.get("sensor.hathway_cycle_start").state == "2026-11-01"
    assert hass.states.get("sensor.hathway_days_until_reset").state == "19"


async def test_auth_failure_starts_reauth(hass, api, entry, ist, freezer):
    await _setup(hass, entry)
    api["status"].side_effect = HathwayAuthError("logged in elsewhere")
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)
    assert entry.state is ConfigEntryState.LOADED


async def test_unload(hass, api, entry, ist):
    await _setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
