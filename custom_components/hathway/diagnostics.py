"""Diagnostics without the session token, mobile number or account number."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_ACCOUNT_NO, CONF_MOBILE, CONF_TOKEN

REDACT = {CONF_TOKEN, CONF_MOBILE, CONF_ACCOUNT_NO}


async def async_get_config_entry_diagnostics(hass, entry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    cycle = coordinator.cycle()
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), REDACT),
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": coordinator.update_interval.total_seconds(),
        "cycle": {"start": cycle.start.isoformat(), "next_reset": cycle.next_reset.isoformat(),
                  "length_days": cycle.length_days},
        "account": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in asdict(data.account).items()} if data else None,
        "latest_day": ({k: (v.isoformat() if hasattr(v, "isoformat") else v)
                        for k, v in asdict(data.latest_day).items()}
                       if data and data.latest_day else None),
    }
