"""Home Assistant tests (pytest-homeassistant-custom-component)."""
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hathway.api import AccountStatus, DayUsage, OtpChallenge
from custom_components.hathway.const import CONF_ACCOUNT_NO, CONF_MOBILE, CONF_TOKEN, DOMAIN
from datetime import date, datetime, timezone
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = ["pytest_homeassistant_custom_component"]

ACCOUNT = AccountStatus(
    used_mb=2562822, total_mb=3585024, quota_label="3501 GB",
    counter_updated=datetime(2026, 11, 12, 2, 14, tzinfo=timezone.utc),
    plan_name="MEGA 400", plan_speed="450 Mbps /450 Mbps", plan_type="Prepaid",
    plan_start=datetime(2026, 10, 23, 18, 30, tzinfo=timezone.utc),
    plan_end=datetime(2027, 10, 25, 13, 0, tzinfo=timezone.utc), plan_days_left=347,
    fup_status="Within Limit", service_status="Active", last_payment_amount=12000.0,
    last_payment_date=datetime(2026, 10, 24, 6, 56, tzinfo=timezone.utc),
)
DAY = DayUsage(day=date(2026, 11, 12), total_bytes=163997432364,
               downloaded_bytes=157135396111, uploaded_bytes=6862036253)
DATA = {CONF_MOBILE: "9000000001", CONF_ACCOUNT_NO: "1000000001", CONF_TOKEN: "t" * 40}
CHALLENGE = OtpChallenge(mobile="9000000001", accounts=["1000000001"], encrypted_mobile="x")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def ist(hass):
    await hass.config.async_set_time_zone("Asia/Kolkata")


@pytest.fixture
def api():
    with patch("custom_components.hathway.api.HathwayClient.account_status",
               AsyncMock(return_value=ACCOUNT)) as status, \
         patch("custom_components.hathway.api.HathwayClient.daily_usage",
               AsyncMock(return_value=[DAY])) as usage, \
         patch("custom_components.hathway.api.HathwayClient.request_otp",
               AsyncMock(return_value=CHALLENGE)) as otp, \
         patch("custom_components.hathway.api.HathwayClient.login",
               AsyncMock(return_value="n" * 40)) as login:
        yield {"status": status, "usage": usage, "otp": otp, "login": login}


@pytest.fixture
def entry(hass):
    e = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="1000000001",
                        title="Hathway 1000000001")
    e.add_to_hass(hass)
    return e
