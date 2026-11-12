# Brand images

`custom_components/hathway/brand/` holds the images Home Assistant shows for this
integration (Home Assistant 2026.3 and newer serve them straight from that folder,
also when offline):

| File | Contents |
|---|---|
| `logo.png`, `logo@2x.png` | Hathway wordmark, 128 and 256 px tall |
| `dark_logo.png`, `dark_logo@2x.png` | Wordmark with white letters for dark themes |
| `icon.png`, `icon@2x.png` | The red "@" from the wordmark, 256 and 512 px square |

They are generated from `docs/brand/hathway-logo.svg`, the logo published on
hathway.com (`/home_images/logo.svg`), by `tools/make_brand.sh`. Hathway is not in
the [Home Assistant brands project](https://github.com/home-assistant/brands).

The Hathway name and logo belong to Hathway Cable & Datacom Ltd. They identify the
compatible service; this community integration is independent of Hathway. Brand
artwork is not covered by this project's MIT code license.
