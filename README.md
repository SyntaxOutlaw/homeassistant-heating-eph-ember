# EPH Controls for Home Assistant

[![License](https://img.shields.io/github/license/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SyntaxOutlaw/homeassistant-heating-eph-ember?style=flat)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/issues)
[![Last commit](https://img.shields.io/github/last-commit/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/commits)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-green)](https://coff.ee/syntaxoutlaw)

Custom integration for **EPH / EMBER** heating gateways — including legacy **GW01 / EMBER-PS** systems that the [built-in Home Assistant EPH Controls integration](https://www.home-assistant.io/integrations/ephember/) cannot talk to.

UI config flow, secure credential storage, climate entities with **On / Boost / Off** plus a **Schedule** preset, gateway diagnostics, and automatic legacy vs current API detection.

## Compatibility

| | Legacy (`GW01` / `EMBER-PS`) | Current (`pyephember2`) |
| --- | --- | --- |
| Modes **On** / **Boost** / **Off** | Supported | Expected to work |
| **Schedule** preset (3 timed periods) | Supported | Expected to work |
| Target temperature | Supported | Expected to work |
| **Advance** preset | Not available via cloud | Expected to work — untested on hardware |
| Gateway diagnostic sensors | Supported | Expected to work |

**Tested on:** EPH Ember Gateway **GW01** (EMBER-PS) only.

**Current / newer gateways** (anything that is not `deviceType == 1` / `EMBER-PS`) go through the same [`pyephember2`](https://pypi.org/project/pyephember2/) stack as Home Assistant’s built-in integration. They have not been run on real non-GW01 hardware here yet — if the stock `ephember` integration would work for your gateway, this custom component should too (plus UI config and the shared legacy path). Auto-detect can fall back to legacy polling if the current API errors.

Testers with **EMBER-PS2**, **GW04**, **COMBIPACK**, or other gateways are welcome — open an issue with your `sysTemType` / `deviceType` from diagnostics if something misbehaves.

## Why this exists

Home Assistant’s stock [`ephember`](https://www.home-assistant.io/integrations/ephember/) integration targets newer EMBER cloud APIs (`pyephember2`). Older **EMBER-PS / GW01** gateways use a different polling API. This custom component speaks both, picks the right one per home, and is set up entirely in the UI.

## Features

- Config entry + reauth (credentials in HA storage, not YAML)
- Auto API detect (`deviceType == 1` or `sysTemType == EMBER-PS` → legacy)
- Optional override: `auto` / `legacy` / `current`
- Climate per zone:
  - **Modes:** On (permanent), Boost (timed), Off
  - **Presets:** Schedule (follow the Ember timetable); Advance on current-API gateways
- Gateway device info (model / hardware / serial) plus diagnostic sensors (invite code, weather location, frost, online status, …)
- Optional Lovelace card with clearer mode / preset icons
- Hexagonal layout: `domain/` · `ports/` · `into/ha/` · `out/`

### Climate controls (how they map)

| UI | Meaning |
| --- | --- |
| **On** | Permanent on until you change mode |
| **Boost** | Timed boost (default 1 hour) |
| **Off** | Permanently off |
| **Schedule** | Follow the zone’s programmed on/off periods (set in the EMBER app / timeclock) |
| **Advance** | Jump to the next schedule period (current API only; hidden on GW01) |

Schedule times and programs are configured in the **EMBER app** or on the **timeclock** — this integration switches modes and setpoints; it does not edit the timetable graph.

## Install

### Manual / Docker bind-mount

Copy or mount this package into your Home Assistant `custom_components` folder:

```text
config/custom_components/ephember/
```

Example Compose volume (adjust paths to your machine):

```yaml
volumes:
  - ./config:/config
  - /path/to/homeassistant-heating-eph-ember/custom_components/ephember:/config/custom_components/ephember
```

Restart Home Assistant, then:

**Settings → Devices & services → Add integration → EPH Controls**

Sign in with your EMBER app email and password.

### Migrating off the built-in YAML integration

If you previously used the [official EPH Controls (`ephember`) integration](https://www.home-assistant.io/integrations/ephember/) via YAML, **remove that block** after this custom integration is configured. Leaving both will conflict.

Delete from `configuration.yaml`:

```yaml
# Built-in / legacy Home Assistant ephember — remove this
climate:
  - platform: ephember
    username: YOUR_EMAIL
    password: YOUR_PASSWORD
```

Restart HA. A repair issue will also remind you if the old platform config is still present.

## Dashboard card

Stock climate cards use Home Assistant’s built-in HVAC icons (so **Boost** may show a fan glyph). This integration ships a custom card with clearer controls:

| Control | Icon |
| --- | --- |
| On | fire |
| Boost | rocket |
| Off | power |
| Schedule (preset) | calendar clock |
| Advance (preset) | skip forward |

After installing / restarting, add a card → **Custom: EPH Ember Climate**, pick a zone entity. Hard-refresh the browser if an older card version is cached.

YAML:

```yaml
type: custom:ephember-climate-card
entity: climate.home_downstairs
```

If the card is missing from the picker (YAML-mode Lovelace), add this resource:

```yaml
url: /ephember-local/ephember-climate-card.js?v=1.2.0
type: module
```

## Architecture (for developers)

```text
custom_components/ephember/
  domain/        # HeatingService, models (no HA / HTTP)
  ports/         # EmberGateway ABC
  into/ha/       # config flow, coordinator, climate, sensors, Lovelace card registration
  out/legacy/    # GW01 HTTP (/zones/polling, setModel, boost, …)
  out/current/   # pyephember2 adapter
  www/           # ephember-climate-card.js
```

Legacy state: `POST /zones/polling`. Writes follow the classic `pyephember` payloads (`setTargetTemperature`, `setModel`, `boost`, `cancelBoost`). Home metadata is enriched from `/homes/detail` (invite code, weather, frost, …).

## Development & testing

Domain and gateway adapters are unit-tested without Home Assistant installed. HA entrypoints load lazily so `pytest` can import `domain/` / `ports/` / `out/` cleanly.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest tests/domain -q
```

What the suite covers today:

- API kind detection (legacy vs current) and fallback
- Legacy `/zones/polling` and `/homes/detail` mapping (temps, modes, demand, `-300` sentinel, gateway metadata)
- HeatingService command routing (mode, setpoint, boost, advance)

There are no live-cloud tests in CI — do not commit EMBER credentials. For a manual check against hardware:

1. Mount or copy `custom_components/ephember` into a Home Assistant instance (see Install).
2. Add the integration via the UI with a test account.
3. Confirm zones appear; try **On**, **Schedule**, **Boost**, and **Off**. On GW01, Advance stays hidden.
4. Download diagnostics from the integration (password / tokens should be redacted) if filing an issue.

When adding gateway types, prefer fixtures under `tests/` over hitting the live API in unit tests.

## Security

- Password lives in Home Assistant `.storage/core.config_entries`
- Access / refresh tokens stay in memory only
- Diagnostics redact `password`, `token`, and `refresh_token`

## Support

Issues and PRs welcome: [github.com/SyntaxOutlaw/homeassistant-heating-eph-ember](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember)

If this saved you a cold house (or a weekend of reverse-engineering), you can [buy me a coffee](https://coff.ee/syntaxoutlaw).

## License

MIT — see [LICENSE](LICENSE).
