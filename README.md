# EPH Controls for Home Assistant

[![License](https://img.shields.io/github/license/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SyntaxOutlaw/homeassistant-heating-eph-ember?style=flat)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/issues)
[![Last commit](https://img.shields.io/github/last-commit/SyntaxOutlaw/homeassistant-heating-eph-ember)](https://github.com/SyntaxOutlaw/homeassistant-heating-eph-ember/commits)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-green)](https://coff.ee/syntaxoutlaw)

Custom integration for **EPH / EMBER** heating gateways — including legacy **GW01 / EMBER-PS** systems that the [built-in Home Assistant EPH Controls integration](https://www.home-assistant.io/integrations/ephember/) cannot talk to.

UI config flow, secure credential storage, climate entities with **Boost** and **Advance**, and automatic legacy vs current API detection.

## Compatibility

| | Legacy (`GW01` / `EMBER-PS`) | Current (`pyephember2`) |
| --- | --- | --- |
| Modes (Auto / Off / All day) | Supported | Expected to work |
| Target temperature | Supported | Expected to work |
| Boost | Supported | Expected to work |
| Advance | **Not available** via cloud (use the timeclock) | Wired through `pyephember2` — untested on hardware |

**Tested on:** EPH Ember Gateway **GW01** (EMBER-PS) only.

**Current / newer gateways** (anything that is not `deviceType == 1` / `EMBER-PS`) go through the same [`pyephember2`](https://pypi.org/project/pyephember2/) stack as Home Assistant’s built-in integration: mode, setpoint, boost, and advance calls are implemented against that library. They have not been run on real non-GW01 hardware here yet, but the path is the standard one — if the stock `ephember` integration would work for your gateway, this custom component should too (plus UI config and shared code with the legacy path). Auto-detect can also fall back to legacy polling if the current API errors.

Testers with **EMBER-PS2**, **GW04**, **COMBIPACK**, or other gateways are very welcome — open an issue with your `sysTemType` / `deviceType` from diagnostics if something misbehaves.

## Why this exists

Home Assistant’s stock [`ephember`](https://www.home-assistant.io/integrations/ephember/) integration targets newer EMBER cloud APIs (`pyephember2`). Older **EMBER-PS / GW01** gateways use a different polling API. This custom component speaks both, picks the right one per home, and is set up entirely in the UI.

## Features

- Config entry + reauth (credentials in HA storage, not YAML)
- Auto API detect (`deviceType == 1` or `sysTemType == EMBER-PS` → legacy)
- Optional override: `auto` / `legacy` / `current`
- Climate per zone: modes, setpoint, **Boost**, **Advance**, All day preset
- Hexagonal layout for maintainability: `domain/` · `ports/` · `into/ha/` · `out/`

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

## Architecture (for developers)

```text
custom_components/ephember/
  domain/        # HeatingService, models (no HA / HTTP)
  ports/         # EmberGateway ABC
  into/ha/       # config flow, coordinator, climate
  out/legacy/    # GW01 HTTP (/zones/polling, setModel, boost, …)
  out/current/   # pyephember2 adapter
```

Legacy state: `POST /zones/polling`. Writes follow the classic `pyephember` payloads (`setTargetTemperature`, `setModel`, `boost`, `cancelBoost`).

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
- Legacy `/zones/polling` mapping (temps, modes, demand, `-300` sentinel)
- HeatingService command routing (mode, setpoint, boost, advance)

There are no live-cloud tests in CI — do not commit EMBER credentials. For a manual check against hardware:

1. Mount or copy `custom_components/ephember` into a Home Assistant instance (see Install).
2. Add the integration via the UI with a test account.
3. Confirm zones appear, modes change, and Boost works; on GW01 expect Advance to fail via cloud.
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
