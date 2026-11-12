"""Parsing and crypto. Synthetic data only; no real account details."""
import json
from datetime import date

import pytest

from hathway_lib.api import (HathwayAuthError, HathwayError, _check, decrypt, encrypt,
                             parse_account, parse_otp_challenge, parse_usage)

ACCOUNT = {
    "status": "success", "responseCode": 200,
    "data": [{
        "customer": {"data_usage_x": 2562822, "data_usage_y": 3585024, "quota": "3501 GB",
                     "customer_plan_type": "Prepaid", "updated_on": 1794449669},
        "customer_plan": [{"plan_product_name": "MEGA 400", "plan_speed": "450 Mbps /450 Mbps",
                           "plan_start_date": 1792780200, "plan_end_date": 1824469200,
                           "no_of_days_left": 347}],
        "customer_service": {"service_status": "Active"},
        "fup_status": "Within Limit",
        "last_payment_details": {"amount": "12000.00", "last_payment_date": 1792824998},
    }],
}


def test_roundtrip():
    assert decrypt(encrypt("1234567890")) == "1234567890"
    assert decrypt(encrypt(json.dumps(["1"]))) == '["1"]'


def test_known_ciphertext_shape():
    # AES-CBC with PKCS#7: 10 bytes -> one 16-byte block -> 24 base64 chars.
    assert len(encrypt("1234567890")) == 24


def test_decrypt_garbage():
    with pytest.raises(HathwayError):
        decrypt("not base64!!")


def test_parse_account():
    a = parse_account(ACCOUNT)
    assert (a.used_mb, a.total_mb, a.remaining_mb) == (2562822, 3585024, 1022202)
    assert a.plan_days_left == 347 and a.fup_status == "Within Limit"
    assert a.last_payment_amount == 12000.0
    assert a.plan_end.isoformat() == "2027-10-25T13:00:00+00:00"


def test_parse_account_encrypted_data():
    payload = {"status": "success", "data": encrypt(json.dumps(ACCOUNT["data"]))}
    assert parse_account(payload).used_mb == 2562822


def test_parse_account_missing_counter():
    with pytest.raises(HathwayError):
        parse_account({"data": [{"customer": {}}]})


def test_parse_usage_sorted_ist():
    days = parse_usage({"data": [
        {"total_data": "10", "downloaded": "7", "uploaded": "3", "effective_t": 1794335400},
        {"total_data": "20", "downloaded": "15", "uploaded": "5", "effective_t": 1794421800},
        {"total_data": None, "effective_t": 1794249000},
    ]})
    assert [d.day for d in days] == [date(2026, 11, 12), date(2026, 11, 11)]
    assert days[0].total_bytes == 20 and days[0].uploaded_bytes == 5


def test_otp_challenge_app_4_6_format():
    payload = {"status": "success", "registered_mobile_no": encrypt("9000000001"),
               "accounts": encrypt(json.dumps(["1000000001", "1000000002"])),
               "email": encrypt("a@example.com"), "customer_name": encrypt("Test User")}
    c = parse_otp_challenge("9000000001", payload)
    assert c.accounts == ["1000000001", "1000000002"]
    assert (c.email, c.customer_name) == ("a@example.com", "Test User")


def test_otp_challenge_legacy_format():
    payload = {"status": "success", "registered_mobile_no": encrypt("9000000001"),
               "account_no": ["1000000001"], "email": encrypt("a@example.com"),
               "customer_name": encrypt("Test User")}
    assert parse_otp_challenge("9000000001", payload).accounts == ["1000000001"]


def test_otp_challenge_nested_data():
    payload = {"status": "success", "data": {"registered_mobile_no": "x",
                                             "accounts": encrypt('["1000000001"]')}}
    assert parse_otp_challenge("9000000001", payload).accounts == ["1000000001"]


def test_otp_challenge_no_account():
    with pytest.raises(HathwayError):
        parse_otp_challenge("9000000001", {"status": "success", "registered_mobile_no": "x"})


def test_check():
    assert _check({"status": "success"})
    with pytest.raises(HathwayAuthError):
        _check({"status": "failure", "responseCode": 401,
                "responseMessage": "You are already logged in from another device!"})
    with pytest.raises(HathwayError) as err:
        _check({"status": "failure", "responseCode": 500, "responseMessage": "x"})
    assert not isinstance(err.value, HathwayAuthError)
    with pytest.raises(HathwayAuthError):
        _check({"status": "failure", "responseCode": 400}, auth_endpoint=True)


def test_unlimited_plan():
    payload = json.loads(json.dumps(ACCOUNT))
    payload["data"][0]["customer"].update(data_usage_x=0, data_usage_y=0, quota="Unlimited")
    a = parse_account(payload)
    assert a.unlimited and a.remaining_mb is None
    assert not parse_account(ACCOUNT).unlimited
