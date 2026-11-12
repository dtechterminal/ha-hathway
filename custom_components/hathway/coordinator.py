"""Polls Hathway for the quota counter and the latest daily usage."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import IST, AccountStatus, DayUsage, HathwayAuthError, HathwayClient, HathwayError
from .const import (CONF_ACCOUNT_NO, CONF_MOBILE, CONF_RESET_DAY, CONF_SCAN_MINUTES,
                    CONF_TOKEN, DEFAULT_RESET_DAY, DEFAULT_SCAN_MINUTES, DOMAIN)
from .cycle import Cycle, cycle_for

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HathwayData:
    account: AccountStatus
    latest_day: DayUsage | None


class HathwayCoordinator(DataUpdateCoordinator[HathwayData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = entry.options.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(minutes=minutes))
        self.client = HathwayClient(
            async_get_clientsession(hass),
            mobile=entry.data[CONF_MOBILE],
            account_no=entry.data[CONF_ACCOUNT_NO],
            token=entry.data[CONF_TOKEN],
        )

    @property
    def reset_day(self) -> int:
        return int(self.config_entry.options.get(CONF_RESET_DAY, DEFAULT_RESET_DAY))

    def cycle(self) -> Cycle:
        return cycle_for(dt_util.now().date(), self.reset_day)

    async def _async_update_data(self) -> HathwayData:
        try:
            account = await self.client.account_status()
        except HathwayAuthError as err:
            raise ConfigEntryAuthFailed(
                "Hathway signed this session out (it allows one login at a time; "
                f"signing in on the Hathway app ends it): {err}") from err
        except HathwayError as err:
            raise UpdateFailed(str(err)) from err
        latest = None
        today = dt_util.now().astimezone(IST).date()
        try:
            days = await self.client.daily_usage(today - timedelta(days=2), today)
            latest = days[0] if days else None
        except HathwayError as err:  # the counter is what matters; keep going
            _LOGGER.debug("Daily usage unavailable: %s", err)
            if self.data:
                latest = self.data.latest_day
        return HathwayData(account=account, latest_day=latest)
