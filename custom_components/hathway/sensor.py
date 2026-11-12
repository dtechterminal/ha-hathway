"""Hathway quota, billing-cycle and plan sensors.

Hathway's "MB" and "GB" are binary units: the 3501 GB quota is 3,585,024 MB.
Data sizes are therefore reported in MiB/GiB.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription, SensorStateClass)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.util import dt as dt_util

from .api import IST
from .coordinator import HathwayCoordinator
from .cycle import projected_usage
from .entity import HathwayEntity

GIB = 1024  # MiB per GiB


def _cycle_attrs(c: HathwayCoordinator) -> dict[str, Any]:
    cycle, today = c.cycle(), dt_util.now().date()
    return {
        "cycle_start": cycle.start.isoformat(),
        "next_reset": cycle.next_reset.isoformat(),
        "cycle_length_days": cycle.length_days,
        "days_elapsed": cycle.days_elapsed(today),
        "reset_day": c.reset_day,
    }


def _projection(c: HathwayCoordinator) -> float | None:
    return projected_usage(c.data.account.used_mb, c.cycle(), dt_util.now())


def _projection_attrs(c: HathwayCoordinator) -> dict[str, Any]:
    account, cycle = c.data.account, c.cycle()
    elapsed = cycle.elapsed_fraction_days(dt_util.now())
    projected = _projection(c)
    return {
        "daily_average_gib": round(account.used_mb / GIB / elapsed, 1) if projected else None,
        "projected_percentage": (round(projected / account.total_mb * 100, 1)
                                 if projected and account.total_mb else None),
        "quota_gib": round(account.total_mb / GIB, 1),
        "cycle_length_days": cycle.length_days,
    }


def _ist_date(value: datetime | None) -> date | None:
    return value.astimezone(IST).date() if value else None


def _latest_attrs(c: HathwayCoordinator) -> dict[str, Any]:
    day = c.data.latest_day
    if not day:
        return {}
    return {"date": day.day.isoformat(),
            "downloaded_gib": round(day.downloaded_bytes / 1024**3, 2),
            "uploaded_gib": round(day.uploaded_bytes / 1024**3, 2)}


@dataclass(frozen=True, kw_only=True)
class HathwaySensorDescription(SensorEntityDescription):
    value_fn: Callable[[HathwayCoordinator], Any]
    attrs_fn: Callable[[HathwayCoordinator], dict[str, Any]] | None = None


DATA_SIZE = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "native_unit_of_measurement": UnitOfInformation.MEBIBYTES,
    "suggested_unit_of_measurement": UnitOfInformation.GIBIBYTES,
    "suggested_display_precision": 1,
}

SENSORS: tuple[HathwaySensorDescription, ...] = (
    HathwaySensorDescription(
        key="data_used", **DATA_SIZE, state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.data.account.used_mb,
        attrs_fn=lambda c: {"quota": c.data.account.quota_label, **_cycle_attrs(c)},
    ),
    HathwaySensorDescription(
        key="data_remaining", **DATA_SIZE, state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.account.remaining_mb,
    ),
    HathwaySensorDescription(
        key="data_quota", **DATA_SIZE,
        value_fn=lambda c: c.data.account.total_mb,
    ),
    HathwaySensorDescription(
        key="usage_percentage", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        value_fn=lambda c: (round(c.data.account.used_mb / c.data.account.total_mb * 100, 1)
                            if c.data.account.total_mb else None),
    ),
    HathwaySensorDescription(
        key="projected_usage", **DATA_SIZE,
        value_fn=_projection, attrs_fn=_projection_attrs,
    ),
    HathwaySensorDescription(
        key="days_until_reset", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS, suggested_display_precision=0,
        value_fn=lambda c: c.cycle().days_until_reset(dt_util.now().date()),
        attrs_fn=_cycle_attrs,
    ),
    HathwaySensorDescription(
        key="cycle_start", device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.cycle().start,
    ),
    HathwaySensorDescription(
        key="next_reset", device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.cycle().next_reset,
    ),
    HathwaySensorDescription(
        key="latest_day_usage", device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.latest_day.total_bytes if c.data.latest_day else None,
        attrs_fn=_latest_attrs,
    ),
    HathwaySensorDescription(
        key="expiry_date", device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: _ist_date(c.data.account.plan_end),
        attrs_fn=lambda c: {"days_left": c.data.account.plan_days_left},
    ),
    HathwaySensorDescription(
        key="plan",
        value_fn=lambda c: c.data.account.plan_name,
        attrs_fn=lambda c: {"speed": c.data.account.plan_speed,
                            "plan_type": c.data.account.plan_type,
                            "plan_start": (d.isoformat() if (d := _ist_date(
                                c.data.account.plan_start)) else None)},
    ),
    HathwaySensorDescription(
        key="fup_status", value_fn=lambda c: c.data.account.fup_status,
    ),
    HathwaySensorDescription(
        key="last_payment", device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="INR", suggested_display_precision=2,
        value_fn=lambda c: c.data.account.last_payment_amount,
        attrs_fn=lambda c: {"date": (d.isoformat() if (d := _ist_date(
            c.data.account.last_payment_date)) else None)},
    ),
    HathwaySensorDescription(
        key="counter_updated", device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.account.counter_updated,
    ),
    HathwaySensorDescription(
        key="service_status", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.account.service_status,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: HathwayCoordinator = entry.runtime_data
    async_add_entities(HathwaySensor(coordinator, d) for d in SENSORS)


class HathwaySensor(HathwayEntity, SensorEntity):
    entity_description: HathwaySensorDescription

    def __init__(self, coordinator: HathwayCoordinator,
                 description: HathwaySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator) if fn else None
