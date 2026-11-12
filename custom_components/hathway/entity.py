"""Shared device identity."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACCOUNT_NO, DOMAIN, MANUFACTURER
from .coordinator import HathwayCoordinator


class HathwayEntity(CoordinatorEntity[HathwayCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HathwayCoordinator, key: str) -> None:
        super().__init__(coordinator)
        account = coordinator.config_entry.data[CONF_ACCOUNT_NO]
        self._attr_unique_id = f"{account}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account)},
            name="Hathway",
            manufacturer=MANUFACTURER,
            model=coordinator.data.account.plan_name or "Broadband",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://selfcare.hathway.com/",
        )
