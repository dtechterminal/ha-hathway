"""Hathway Broadband data quota and billing cycle."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .coordinator import HathwayCoordinator

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HathwayConfigEntry = ConfigEntry[HathwayCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HathwayConfigEntry) -> bool:
    coordinator = HathwayCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _new_day(_now) -> None:
        # Cycle dates and day counts change at local midnight, between polls.
        coordinator.async_update_listeners()

    entry.async_on_unload(async_track_time_change(hass, _new_day, hour=0, minute=0, second=5))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: HathwayConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HathwayConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
