# Hathway Broadband for Home Assistant

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/hathway/brand/dark_logo@2x.png">
  <img src="custom_components/hathway/brand/logo@2x.png" alt="Hathway" width="240">
</picture>

Shows your Hathway broadband data quota in Home Assistant, together with the
billing cycle it belongs to: how much of the month's quota is used, how many days
are left until it resets, and where usage is heading by the reset date.

It signs in the same way the Hathway Broadband app does, with your registered
mobile number and an SMS OTP, and reads the same counter the app shows.

## Sensors

| Sensor | What it shows |
|---|---|
| Data used | Quota used this cycle (GiB). Hathway's own counter, uploads included |
| Data remaining / Data quota | Left this cycle, and the cycle's allowance |
| Usage percentage | Used ÷ quota |
| Projected usage | Usage at the reset date at the current daily average. Unknown on the reset day itself |
| Days until reset | Days to the next quota reset, with cycle start, length and days elapsed as attributes |
| Cycle start / Next reset | Dates of the current cycle |
| Latest day usage | Hathway's most recent daily record, with download and upload split |
| Expiry date | When the paid plan ends |
| Plan, FUP status, Last payment | Plan name and speed, fair-usage state, last payment |
| Counter updated, Service status | Diagnostics |

Hathway counts data in binary units (its "3501 GB" quota is 3,585,024 MB), so data
sizes are in GiB.

## Installation

### HACS

Add this repository as a custom repository in HACS (category: Integration), install
**Hathway Broadband**, then restart Home Assistant.

### Manual

Copy `custom_components/hathway` into your Home Assistant `config/custom_components/`
folder and restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration → Hathway Broadband.**
2. Choose **Sign in with an SMS OTP**, enter the registered mobile number, then the OTP.
   If several accounts share the number, pick one.
3. Open the integration's **Configure** to set the **quota reset day** (default 26)
   and the refresh interval (default 60 minutes).

**One session at a time.** Hathway allows one active login per account. Signing in
here signs the Hathway app out. If someone later signs in on the app, this
integration's session ends and Home Assistant shows a re-authentication prompt that
sends a new OTP.

**Existing token.** If you already have a session token (for example from a script),
choose **Use an existing session token** to move it over without an SMS.

## Automations

Use the cycle sensors instead of fixed-length date maths. Hathway resets on a day of
the month, so cycles are 28 to 31 days long:

```yaml
- alias: Data pacing warning
  triggers:
    - trigger: time
      at: "20:00:00"
  conditions:
    - condition: template
      value_template: >
        {{ has_value('sensor.hathway_projected_usage')
           and state_attr('sensor.hathway_projected_usage', 'projected_percentage') | float(0) > 95 }}
  actions:
    - action: notify.notify
      data:
        message: >
          At this pace you'll use {{ states('sensor.hathway_projected_usage') | float | round(0) }} GiB
          of {{ state_attr('sensor.hathway_projected_usage', 'quota_gib') | round(0) }} GiB.
          {{ states('sensor.hathway_days_until_reset') }} days until reset.
```

## Privacy

The session token, mobile number and account number stay in Home Assistant's
config entry and are redacted from diagnostics. The integration only talks to
`ispselfcareadmin.hathway.net`.

## Development

```sh
pip install pytest pytest-asyncio aiohttp cryptography ruff
pytest -q tests            # API parsing, encryption, cycle maths (no Home Assistant)
pip install pytest-homeassistant-custom-component
pytest -q tests_ha         # config flow, sensors, re-authentication
```

`docs/api.md` describes the endpoints and encryption. `docs/branding.md` explains
the images in `brand/` and how `tools/make_brand.sh` rebuilds them.

This is an independent community project, not affiliated with or endorsed by
Hathway Cable & Datacom Ltd. The Hathway name and logo are their trademarks, used
here only to identify the compatible service.
