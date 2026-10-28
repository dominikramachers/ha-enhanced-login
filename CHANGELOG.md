# Changelog

## 0.1.2

- Fix: the particle background is now also shown on the SSO choice page (and the other
  hass-oidc-auth pages), so it is present in the whole sign-in flow. The stock sign-in page keeps
  drawing its own particles.
- Fix: the "Back" link on the local login was unstyled (class name mismatch between script and
  stylesheet). Tests now guard against such mismatches.
- Screenshots in the README.

## 0.1.1

- Fix: a `logo` inside the configuration folder (for example `logo.png`) was rejected because
  Home Assistant's default allowlist only covers `www` and `media`. Files inside the
  configuration folder are now accepted; paths outside it still need `allowlist_external_dirs`.

## 0.1.0

First public release.

- Unified, theme-aware design for `/auth/authorize` (username/password, MFA) and the pages of
  [hass-oidc-auth](https://github.com/christiaangoossens/hass-oidc-auth) (`/auth/oidc/*`).
- Colors follow the default Home Assistant theme, light and dark.
- German and English texts for the OIDC pages (language from the Home Assistant settings).
- Whole-field red state for invalid or required fields, "Back" link from the local login to the
  SSO / local choice.
- Optional custom logo, tile color and favicon (sign-in pages and the whole UI).
- Fail-open: any error serves the original page; `?el=0` disables the changes per request.
- Startup check with a persistent notification if the sign-in page could not be enhanced.
