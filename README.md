# FreeMyIP Integration for Home Assistant

Custom integration to update a `*.freemyip.com` dynamic DNS domain from Home Assistant.

## What this port does

- Uses the FreeMyIP updater endpoint: `https://freemyip.com/update`
- Uses FreeMyIP check IP endpoint: `https://freemyip.com/checkip`
- Authenticates with `token` + `domain` (no API key required)
- Supports economy mode (update only when IP changed)
- Supports optional IPv6 update when available

## Requirements

- Home Assistant with `custom_components`
- A FreeMyIP dynamic domain
- Your FreeMyIP update token

## Installation

1. Copy `custom_components/freemyip` to your HA config folder as `custom_components/freemyip`.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration**.
4. Search for **FreeMyIP**.
5. Fill in:
   - Domain (example: `myhome.freemyip.com`)
   - Token
   - Economy mode (optional)
   - IPv6 support (optional)
   - Update interval

## Service

- `freemyip.refresh`: force a refresh/update.

Optional field:

- `economy` (boolean): only perform updater call when IP changed.

## Notes about FreeMyIP behavior

- Updater result returns `OK` or `ERROR`.
- `verbose=yes` is used by the integration for diagnostics.
- For explicit target IP updates, FreeMyIP accepts `myip` (IPv4 or IPv6).

## Debug logs

```yaml
logger:
  logs:
    custom_components.freemyip: debug
```
