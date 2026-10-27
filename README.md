# Enhanced Login for Home Assistant

[![Tests](https://github.com/dominikramachers/ha-enhanced-login/actions/workflows/tests.yml/badge.svg)](https://github.com/dominikramachers/ha-enhanced-login/actions/workflows/tests.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A unified, theme-aware design for the Home Assistant sign-in. It restyles

- the regular sign-in page (`/auth/authorize`: username/password, MFA), and
- the pages of [hass-oidc-auth](https://github.com/christiaangoossens/hass-oidc-auth)
  (`/auth/oidc/welcome`, the companion-app code page, the error and success pages),

so that a single-sign-on setup (for example Microsoft Entra ID) looks like one coherent product
instead of three different pages.

## Features

- **Follows your Home Assistant theme.** Colors are generated live from the *default* theme (light
  and dark), with a built-in fallback palette.
- **Two-column layout** with a logo tile, inputs and buttons with 54 px touch targets, a single
  column with a logo banner on narrow screens, particle background kept (subtle).
- **Clear form states:** invalid or required fields turn red as a whole field; a **Back** link
  leads from the local login back to the SSO / local choice.
- **Localized texts** for the hass-oidc-auth pages: German and English (taken from the Home
  Assistant language setting). Other languages show the English texts.
- **Your own logo, tile color and favicon** (optional), applied to the sign-in pages and,
  optionally, the whole UI.
- **Fail-open by design.** Any error serves the original page unchanged, so you can never lock
  yourself out. `?el=0` on a URL disables all changes for that request.
- **Update check.** About 90 seconds after startup the integration verifies that the sign-in page
  is really enhanced and creates a persistent notification if it is not (for example after a
  Home Assistant or hass-oidc-auth update that changed internals).
- Does not modify hass-oidc-auth or Home Assistant files, so it survives their updates.

## Requirements

- Home Assistant 2024.7 or newer (the minimum API level used; developed and tested with 2026.10).
- hass-oidc-auth is **optional**. Without it, only the regular sign-in page is restyled.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/dominikramachers/ha-enhanced-login`
   with category **Integration**.
2. Install **Enhanced Login** and restart Home Assistant.
3. Add the integration to `configuration.yaml` (see below) and restart again.

### Manual

Copy `custom_components/enhanced_login` into the `custom_components` folder of your Home Assistant
configuration, add the YAML below and restart.

## Configuration

The integration is configured in `configuration.yaml` (there is no config flow, because it must be
active before anyone has signed in). The minimal configuration is:

```yaml
enhanced_login:
```

All options are optional:

```yaml
enhanced_login:
  logo: www/my-logo.png     # PNG, JPG, WebP, GIF or SVG, max 2 MB; relative to the config folder
  tile_color: "#0F172A"     # background of the logo tile (hex)
  favicon: true             # use the logo as favicon (see below)
```

| Option       | Default                | Description |
|--------------|------------------------|-------------|
| `logo`       | bundled placeholder    | Path to your logo. Relative paths start in the Home Assistant configuration folder; absolute paths must be allowed by `allowlist_external_dirs`. A transparent logo with a wide aspect ratio (about 6:5) works best. |
| `tile_color` | `#0F172A`              | Color behind the logo, also used as the background of the favicon. |
| `favicon`    | `true` if `logo` is set, else `false` | Replaces the browser icon on the sign-in pages **and in the whole Home Assistant UI** with an icon rendered from the logo. The bundled placeholder never replaces your favicon unless you set `favicon: true`. |

Changes to these options need a restart of Home Assistant.

### Theme

Colors come from the *default* theme and the *default dark* theme (the ones set with the
`frontend.set_theme` action; the sign-in page has no user, so user themes cannot apply). The
integration reads the standard variables (`primary-color`, `card-background-color`,
`primary-text-color`, `secondary-text-color`, `error-color`, `divider-color`, …) and these optional
ones, which you can add to a theme to fine-tune the sign-in pages:

| Theme variable    | Purpose |
|-------------------|---------|
| `el-page-bg`      | Page background (defaults to `primary-background-color`) |
| `el-border`       | Border color (defaults to `divider-color`) |
| `el-border-strong`| Stronger border (inputs, outlined buttons) |

Example:

```yaml
frontend:
  themes:
    my_theme:
      primary-color: "#175CD3"
      el-page-bg: "#F3F4F6"
```

## Safety and troubleshooting

- **Locked out or something looks wrong?** Open the page with `?el=0` appended, for example
  `https://ha.example.com/auth/authorize?el=0`. Remove `enhanced_login:` from `configuration.yaml`
  and restart to switch the integration off completely.
- **Notification "Enhanced Login is not active"** means the sign-in routes could not be wrapped.
  Sign-in keeps working with the original design. Check the release notes for a version that
  supports your Home Assistant version, and open an issue with your Home Assistant and
  hass-oidc-auth versions if none exists.
- **Browser cache:** after installing or upgrading, reload the sign-in page with <kbd>Ctrl</kbd>+<kbd>F5</kbd>.
- **Logs:** `Enhanced Login: N sign-in routes wrapped` appears at startup.

## How it works

Home Assistant freezes its HTTP middleware list before custom integrations start, and the sign-in
pages are served by core and by hass-oidc-auth. Enhanced Login therefore wraps the handlers of the
routes `/auth/authorize` and `/auth/oidc/*` (the same technique hass-oidc-auth uses), lets the
original handler produce the page, and then:

1. translates the hass-oidc-auth texts (German),
2. injects `theme.css` (generated from your theme), `login.css` and `login.js`,
3. optionally injects the favicon script.

The wrapping runs several times during startup because routes are registered at different points.
Static files are served from `/enhanced-login/`.

This relies on internals (`route._handler`) of aiohttp and Home Assistant. That is why the
integration is fail-open and verifies itself after startup.

## Development

```bash
pip install -r requirements_test.txt
python -m pytest tests -q
```

The tests stub the few Home Assistant modules that are imported, so Home Assistant itself is not
needed to run them. The visual layer has to be checked in a real Home Assistant; the sign-in page
needs a hard reload because it is cached aggressively by browsers.

Issues and pull requests are welcome, especially for additional languages and for new
Home Assistant / hass-oidc-auth versions.

## Deutsch (Kurzfassung)

Einheitliches, theme-abhängiges Design für die Home-Assistant-Anmeldung (normale Anmeldung und
hass-oidc-auth/SSO): Farben aus dem Standard-Theme (hell/dunkel), deutsche Texte für die
SSO-Seiten, ganze Felder rot bei Fehlern, „Zurück“-Link, optional eigenes Logo, Kachelfarbe und
Favicon. Installation über HACS (benutzerdefiniertes Repository), dann in `configuration.yaml`
`enhanced_login:` eintragen und neu starten. Bei Problemen die Seite mit `?el=0` öffnen; die
Integration liefert bei jedem Fehler die Originalseite aus und meldet sich nach Updates mit einer
Benachrichtigung, falls das Design nicht mehr greift.

## License

[MIT](LICENSE)
