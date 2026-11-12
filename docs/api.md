# Hathway self-care API notes

The integration talks to the same endpoints as the Hathway Broadband Android app
(`com.hathwayapp`). Request shapes were read from app version 4.6.4.

| Purpose | Endpoint | Auth |
|---|---|---|
| Request OTP | `POST /api/isp/v2/customer/generateotp` | none |
| Send the OTP SMS | `POST /api/isp/v1/customer/sendOtpOnPhoneNumber` | none |
| Log in with OTP / account info | `POST /api/isp/v2/customer/login` | token for `use: info` |
| Daily usage | `POST /api/isp/v1/customer/usagedetails` | token |
| Register app version | `POST /api/isp/v1/version/saveAppVersion` | token |

Base URL: `https://ispselfcareadmin.hathway.net`. Headers: `Accept` and
`Content-Type: application/json`, `version: 4.6.4`, `device_type: 1` (Android),
`Authorization: <token>` where needed.

## Encryption

The app uses CryptoJS AES-256-CBC with PKCS#7 padding and fixed, app-wide
parameters (`EncryptDecryptStore` in the Hermes bundle). `api.encrypt` and
`api.decrypt` implement the same.

- `generateotp` body: `{"input": encrypt(JSON.stringify({type: "registered_mobile_no", input_value: <mobile>, login_device: "mobile"}))}`.
- Its response holds `accounts` (encrypted JSON list), `email`, `customer_name` and
  `registered_mobile_no`, all encrypted. Older responses carried a plain
  `account_no` list; both are accepted.
- `sendOtpOnPhoneNumber` body: the decrypted `registered_mobile_no` (as a number),
  `email` and `customer_name`.
- `login` body: `registered_mobile_no` = encrypt(mobile), `otp`,
  `login_device: "mobile"`, `account_no` = encrypt(account number). The response
  carries `token`.

## Sessions

Hathway keeps one session per account. A new OTP login anywhere (the app, or this
integration) invalidates the previous token, and API calls with the old token
return `{"responseCode": 401, "responseMessage": "You are already logged in from
another device!"}`. The integration turns that into a Home Assistant re-authentication
request.

## Units and the quota counter

`customer.data_usage_x` (used) and `data_usage_y` (quota) are in binary MB: the
"3501 GB" quota is 3,585,024 MB. The counter resets to 0 on a fixed day each month
(the 26th for the account this was built against; it reset between 01:00 and 18:00
IST on that day across May to Oct 2026). `usagedetails` returns per-day byte totals
labelled by `effective_t` (IST midnight); they cover the whole line, uploads included.
