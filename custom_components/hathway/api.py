"""Client for the Hathway Broadband self-care API used by the official Android app.

The request shapes match Hathway Broadband 4.6.4 (com.hathwayapp): the OTP
request is AES-256-CBC encrypted into a single ``input`` field, and the OTP
response returns the account list, name, e-mail and mobile number encrypted
with the same key. No Home Assistant imports, so this module is unit-tested
directly.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://ispselfcareadmin.hathway.net/api/isp"
URL_GENERATE_OTP = f"{BASE_URL}/v2/customer/generateotp"
URL_SEND_OTP_PHONE = f"{BASE_URL}/v1/customer/sendOtpOnPhoneNumber"
URL_LOGIN = f"{BASE_URL}/v2/customer/login"
URL_USAGE = f"{BASE_URL}/v1/customer/usagedetails"
URL_SAVE_APP_VERSION = f"{BASE_URL}/v1/version/saveAppVersion"

APP_VERSION = "4.6.4"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "version": APP_VERSION,
    "device_type": "1",  # 1 = Android, 2 = iOS
}

# The app's static AES parameters (EncryptDecryptStore in index.android.bundle).
_KEY = b"H@+HW4Y1SPS3LFC4H@+HW4Y1SPS3LFC4"
_IV = b"1110010011001111"

IST = timezone(timedelta(hours=5, minutes=30))
TIMEOUT = aiohttp.ClientTimeout(total=30)


class HathwayError(Exception):
    """The API could not be reached or returned something unexpected."""


class HathwayAuthError(HathwayError):
    """The session token was rejected, or the OTP was wrong."""


def encrypt(text: str) -> str:
    padder = padding.PKCS7(128).padder()
    data = padder.update(text.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(_KEY), modes.CBC(_IV)).encryptor()
    return base64.b64encode(encryptor.update(data) + encryptor.finalize()).decode()


def decrypt(text: str) -> str:
    try:
        raw = base64.b64decode(text, validate=True)
        decryptor = Cipher(algorithms.AES(_KEY), modes.CBC(_IV)).decryptor()
        data = decryptor.update(raw) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return (unpadder.update(data) + unpadder.finalize()).decode()
    except (binascii.Error, ValueError, UnicodeDecodeError) as err:
        raise HathwayError("Could not decrypt a field in Hathway's response") from err


def _decrypt_or_plain(value: Any) -> Any:
    """Decrypt a field that may be encrypted (app 4.6.x) or plain (older API)."""
    if not isinstance(value, str) or not value:
        return value
    try:
        return decrypt(value)
    except HathwayError:
        return value


@dataclass(frozen=True)
class OtpChallenge:
    """What the OTP request returned; needed to complete the login."""

    mobile: str
    accounts: list[str]
    encrypted_mobile: str
    customer_name: str = field(repr=False, default="")
    email: str = field(repr=False, default="")


@dataclass(frozen=True)
class DayUsage:
    day: date
    total_bytes: int
    downloaded_bytes: int
    uploaded_bytes: int


@dataclass(frozen=True)
class AccountStatus:
    used_mb: int
    total_mb: int
    quota_label: str | None
    counter_updated: datetime | None
    plan_name: str | None
    plan_speed: str | None
    plan_type: str | None
    plan_start: datetime | None
    plan_end: datetime | None
    plan_days_left: int | None
    fup_status: str | None
    service_status: str | None
    last_payment_amount: float | None
    last_payment_date: datetime | None

    @property
    def remaining_mb(self) -> int:
        return max(self.total_mb - self.used_mb, 0)


def _ts(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_account(payload: dict[str, Any]) -> AccountStatus:
    """Parse the ``login`` (use=info) response."""
    data = payload.get("data")
    if isinstance(data, str):  # newer responses may carry the record encrypted
        data = json.loads(decrypt(data))
    if not data or not isinstance(data, list):
        raise HathwayError("Hathway returned no account data")
    record = data[0]
    customer = record.get("customer") or {}
    plans = record.get("customer_plan") or [{}]
    plan = plans[0] or {}
    payment = record.get("last_payment_details") or {}
    service = record.get("customer_service") or {}
    used, total = _int(customer.get("data_usage_x")), _int(customer.get("data_usage_y"))
    if used is None or total is None:
        raise HathwayError("Hathway's response has no data usage counter")
    return AccountStatus(
        used_mb=used,
        total_mb=total,
        quota_label=customer.get("quota"),
        counter_updated=_ts(customer.get("updated_on")),
        plan_name=plan.get("plan_product_name"),
        plan_speed=plan.get("plan_speed"),
        plan_type=customer.get("customer_plan_type"),
        plan_start=_ts(plan.get("plan_start_date")),
        plan_end=_ts(plan.get("plan_end_date")),
        plan_days_left=_int(plan.get("no_of_days_left")),
        fup_status=record.get("fup_status"),
        service_status=service.get("service_status"),
        last_payment_amount=_float(payment.get("amount")),
        last_payment_date=_ts(payment.get("last_payment_date")),
    )


def parse_usage(payload: dict[str, Any]) -> list[DayUsage]:
    """Parse ``usagedetails``; newest day first. Days are labelled in IST."""
    days = []
    for row in payload.get("data") or []:
        stamp, total = _int(row.get("effective_t")), _int(row.get("total_data"))
        if stamp is None or total is None:
            continue
        days.append(DayUsage(
            day=datetime.fromtimestamp(stamp, tz=IST).date(),
            total_bytes=total,
            downloaded_bytes=_int(row.get("downloaded")) or 0,
            uploaded_bytes=_int(row.get("uploaded")) or 0,
        ))
    return sorted(days, key=lambda d: d.day, reverse=True)


def parse_otp_challenge(mobile: str, payload: dict[str, Any]) -> OtpChallenge:
    """Parse ``generateotp``. Fields may sit at the top level or under ``data``."""
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    encrypted_mobile = body.get("registered_mobile_no")
    if not encrypted_mobile:
        raise HathwayError("Hathway did not return the account for this mobile number")
    accounts_field = body.get("accounts", body.get("account_no"))
    accounts_field = _decrypt_or_plain(accounts_field)
    if isinstance(accounts_field, str):
        try:
            accounts_field = json.loads(accounts_field)
        except ValueError:
            accounts_field = [accounts_field]
    accounts = [str(a) for a in (accounts_field or []) if str(a).strip()]
    if not accounts:
        raise HathwayError("No Hathway account is linked to this mobile number")
    return OtpChallenge(
        mobile=mobile,
        accounts=accounts,
        encrypted_mobile=encrypted_mobile,
        customer_name=_decrypt_or_plain(body.get("customer_name")) or "",
        email=_decrypt_or_plain(body.get("email")) or "",
    )


def _check(payload: Any, *, auth_endpoint: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HathwayError("Unexpected response from Hathway")
    code = payload.get("responseCode")
    ok = payload.get("status") == "success" or code == 200
    if ok:
        return payload
    message = payload.get("responseMessage") or "unknown error"
    if code == 401 or auth_endpoint:
        raise HathwayAuthError(message)
    raise HathwayError(f"Hathway API error {code}: {message}")


class HathwayClient:
    """Talks to Hathway with one account's session token."""

    def __init__(self, session: aiohttp.ClientSession, *, mobile: str = "",
                 account_no: str = "", token: str = "") -> None:
        self._session = session
        self.mobile = mobile
        self.account_no = account_no
        self.token = token

    async def _post(self, url: str, body: dict[str, Any], *, auth: bool) -> Any:
        headers = dict(HEADERS)
        if auth:
            headers["Authorization"] = self.token
        try:
            async with self._session.post(url, json=body, headers=headers,
                                          timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    raise HathwayAuthError("Session token rejected")
                if resp.status >= 500:
                    raise HathwayError(f"Hathway server error {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise HathwayError(f"Could not reach Hathway: {err}") from err

    # --- sign-in ----------------------------------------------------------
    async def request_otp(self, mobile: str) -> OtpChallenge:
        inner = {"type": "registered_mobile_no", "input_value": mobile,
                 "login_device": "mobile"}
        payload = _check(await self._post(URL_GENERATE_OTP,
                                          {"input": encrypt(json.dumps(inner))}, auth=False))
        challenge = parse_otp_challenge(mobile, payload)
        # The app then asks for the SMS explicitly, with the decrypted details.
        _check(await self._post(URL_SEND_OTP_PHONE, {
            "registered_mobile_no": int(mobile),
            "email": challenge.email,
            "customer_name": challenge.customer_name,
        }, auth=False))
        return challenge

    async def login(self, challenge: OtpChallenge, otp: str, account_no: str) -> str:
        payload = _check(await self._post(URL_LOGIN, {
            "registered_mobile_no": encrypt(str(int(challenge.mobile))),
            "otp": otp,
            "login_device": "mobile",
            "account_no": encrypt(account_no),
        }, auth=False), auth_endpoint=True)
        token = payload.get("token")
        if not token:
            raise HathwayAuthError("Hathway accepted the OTP but returned no token")
        self.mobile, self.account_no, self.token = challenge.mobile, account_no, token
        try:  # the app registers its version after login; failure is harmless
            await self._post(URL_SAVE_APP_VERSION, {
                "account_no": account_no, "registered_mobile_no": challenge.mobile,
                "device_type": 1, "login_device": "mobile", "app_version": APP_VERSION,
            }, auth=True)
        except HathwayError as err:
            _LOGGER.debug("saveAppVersion failed: %s", err)
        return token

    # --- data -------------------------------------------------------------
    async def account_status(self) -> AccountStatus:
        payload = _check(await self._post(URL_LOGIN, {
            "registered_mobile_no": self.mobile,
            "is_latlong": 1,
            "use": "info",
            "login_device": "mobile",
            "account_no": self.account_no,
        }, auth=True))
        return parse_account(payload)

    async def daily_usage(self, start: date, end: date) -> list[DayUsage]:
        payload = await self._post(URL_USAGE, {
            "login_device": "mobile",
            "account_no": self.account_no,
            "registered_mobile_no": self.mobile,
            "start_date": start.strftime("%d-%m-%Y"),
            "end_date": end.strftime("%d-%m-%Y"),
        }, auth=True)
        if isinstance(payload, dict) and payload.get("responseCode") == 414:
            return []  # "No details found" for the range
        return parse_usage(_check(payload))
