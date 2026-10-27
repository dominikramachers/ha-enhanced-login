# Changelog

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
