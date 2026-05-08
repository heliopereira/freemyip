# FreeMyIP Integration for Home Assistant

![FreeMyIP Logo](images/freemyip_logo.png)

Custom Home Assistant integration to keep a `*.freemyip.com` domain updated with your current public IPv4/IPv6.

## Overview

This integration is focused on one job: reliable dynamic DNS updates for FreeMyIP.

- Uses `https://freemyip.com/update` for domain updates
- Uses `https://freemyip.com/checkip` for public IPv4 detection
- Supports IPv6 detection/update when enabled
- Uses `token` + `domain` only (no API key)
- Supports economy mode (update only when IP changes)

## Requirements

Before installing, make sure you have:

1. A running Home Assistant instance
2. Access to `custom_components` folder
3. A FreeMyIP domain (example: `myhome.freemyip.com`)
4. A valid FreeMyIP update token

## Installation (Manual)

1. Download or clone this repository.
2. Copy the folder `custom_components/freemyip` to your Home Assistant config path:
   - Final path must be: `config/custom_components/freemyip`
3. Restart Home Assistant.
4. In Home Assistant, go to:
   - `Settings` -> `Devices & Services` -> `Add Integration`
5. Search for `FreeMyIP` and open it.
6. Fill in the form fields:
   - `Domain`: your FreeMyIP domain
   - `Token`: secret token value
   - `Economy mode`: optional
   - `IPv6 support`: optional
   - `Update interval`: minutes (0 disables scheduled updates)
7. Finish setup and confirm entities are created.

## Entities Created

The integration creates short-name sensors under device `FreeMyIP <your-domain>`:

- `Status`
- `IPv4`
- `IPv6` (when enabled)
- `Last Update`

## Service

Service available:

- `freemyip.refresh`

Service field:

- `economy` (`boolean`): when `true`, only updates when detected IP changed

Example service call in Developer Tools:

```yaml
service: freemyip.refresh
data:
  economy: true
```

## How Updates Work

- FreeMyIP updater returns `OK` or `ERROR`
- Integration uses `verbose=yes` internally for better diagnostics
- Integration sends `myip` when updating explicit detected IPv4/IPv6

## Troubleshooting

Enable debug logs in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.freemyip: debug
```

Then restart Home Assistant and check logs in:

- `Settings` -> `System` -> `Logs`

## Branding Assets

Project logo file location:

- `images/freemyip_logo.png`

If you replace the logo, keep the same filename/path so README references continue to work.

## Support the Project

If this integration helps you, consider supporting development:

- Ko-fi: `https://ko-fi.com/heliopereira`

Thank you for supporting maintenance, fixes, and new features.
