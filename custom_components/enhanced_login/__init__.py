"""Enhanced Login: a unified, theme-aware design for the Home Assistant sign-in.

Adds a stylesheet and a small script to the sign-in pages (``/auth/authorize``
and the pages of the hass-oidc-auth integration under ``/auth/oidc/``). Colors
come from the default Home Assistant theme (light and dark).

Safety: on any error the original page is delivered unchanged (fail-open).
Appending ``?el=0`` to a URL disables all changes for that request.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import re
from pathlib import Path

from aiohttp import web
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.event import async_call_later
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

DOMAIN = "enhanced_login"

CONF_LOGO = "logo"
CONF_TILE_COLOR = "tile_color"
CONF_FAVICON = "favicon"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            None,
            vol.Schema(
                {
                    vol.Optional(CONF_LOGO): cv.string,
                    vol.Optional(CONF_TILE_COLOR): vol.Match(
                        r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
                    ),
                    vol.Optional(CONF_FAVICON): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

URL = "/enhanced-login"
STATIC_DIR = Path(__file__).parent / "static"
ASSETS = ("login.css", "login.js")  # served as static files
DEFAULT_LOGO = "logo-default.png"
DEFAULT_TILE = "#0F172A"

_LOGO_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}
_LOGO_MAX_BYTES = 2 * 1024 * 1024


@dataclass
class Settings:
    """Resolved configuration and assets (built once at setup)."""

    logo: bytes = b""
    logo_type: str = "image/png"
    logo_hash: str = ""
    tile: str = DEFAULT_TILE
    favicon: bool = False
    favicon_js: str = ""
    version: str = ""


# ---------------------------------------------------------------- Theme ----

# Built-in palette, used when the default theme provides no values.
FALLBACK = {
    "light": {
        "bg": "#F3F4F6",
        "card": "#FFFFFF",
        "text": "#101B2D",
        "muted": "#667085",
        "border": "rgba(16,24,40,0.08)",
        "border-strong": "rgba(16,24,40,0.16)",
        "accent": "#175CD3",
        "error": "#DC2626",
        "particles": "0.12",
    },
    "dark": {
        "bg": "#0D192D",
        "card": "#1B273A",
        "text": "#F1F5F9",
        "muted": "#94A3B8",
        "border": "rgba(255,255,255,0.10)",
        "border-strong": "rgba(255,255,255,0.18)",
        "accent": "#4C8DF6",
        "error": "#F87171",
        "particles": "0.35",
    },
}

_SAFE_VALUE = re.compile(r"^[#\w\s.,()%/+\-]{1,120}$")


def _safe(value: object) -> bool:
    """Accept only harmless CSS values from the theme."""
    if not isinstance(value, str) or not _SAFE_VALUE.match(value):
        return False
    low = value.lower()
    return "url(" not in low and "expression" not in low and "@import" not in low


def _tokens(theme: object, mode: str) -> dict[str, str]:
    """Derive the design values for one mode (light/dark) from an HA theme.

    A theme can override the page background and the borders with the
    optional variables ``el-page-bg``, ``el-border`` and ``el-border-strong``.
    """
    flat: dict[str, str] = {}
    if isinstance(theme, dict):
        flat = {k: v for k, v in theme.items() if k != "modes" and isinstance(v, str)}
        modes = theme.get("modes")
        if isinstance(modes, dict) and isinstance(modes.get(mode), dict):
            flat.update({k: v for k, v in modes[mode].items() if isinstance(v, str)})

    fb = FALLBACK[mode]

    def pick(*keys: str, default: str) -> str:
        for key in keys:
            value = flat.get(key)
            if value and _safe(value):
                return value.strip()
        return default

    return {
        "bg": pick("el-page-bg", "dl-page-bg", "primary-background-color", default=fb["bg"]),
        "card": pick("card-background-color", default=fb["card"]),
        "text": pick("primary-text-color", default=fb["text"]),
        "muted": pick("secondary-text-color", default=fb["muted"]),
        "border": pick("el-border", "dl-border", "divider-color", default=fb["border"]),
        "border-strong": pick(
            "el-border-strong",
            "dl-border-strong",
            default="color-mix(in srgb, var(--el-text) 18%, transparent)",
        ),
        "accent": pick("primary-color", default=fb["accent"]),
        "on-accent": pick("text-primary-color", default="#FFFFFF"),
        "error": pick("error-color", default=fb["error"]),
        "particles": fb["particles"],
    }


def _block(tokens: dict[str, str], mode: str) -> str:
    body = "".join(f"--el-{key}:{value};" for key, value in tokens.items())
    return f":root{{{body}color-scheme:{mode};}}"


def build_theme_css(hass: HomeAssistant, settings: Settings) -> str:
    """CSS with the design values from the default theme (light and dark)."""
    themes = hass.data.get("frontend_themes") or {}
    light_name = hass.data.get("frontend_default_theme")
    dark_name = hass.data.get("frontend_default_dark_theme") or light_name
    if not isinstance(themes, dict):
        themes = {}

    extra = {
        "tile": settings.tile,
        "logo": f"url({URL}/logo?v={settings.logo_hash})",
    }
    light = {**_tokens(themes.get(light_name), "light"), **extra}
    dark = {**_tokens(themes.get(dark_name), "dark"), **extra}
    return (
        "/* Enhanced Login - generated from the default theme */\n"
        + _block(light, "light")
        + "\n@media (prefers-color-scheme: dark){"
        + _block(dark, "dark")
        + "}\n"
    )


class ThemeView(HomeAssistantView):
    """Serves the theme CSS (no auth: the page itself is the sign-in)."""

    requires_auth = False
    url = f"{URL}/theme.css"
    name = "enhanced_login:theme"

    def __init__(self, hass: HomeAssistant, settings: Settings) -> None:
        self._hass = hass
        self._settings = settings

    async def get(self, request: web.Request) -> web.Response:
        try:
            css = build_theme_css(self._hass, self._settings)
        except Exception:  # noqa: BLE001 - never block the sign-in
            _LOGGER.exception("Could not build the theme CSS")
            css = ""
        return web.Response(
            text=css,
            content_type="text/css",
            headers={"Cache-Control": "no-cache"},
        )


class LogoView(HomeAssistantView):
    """Serves the logo (configured file or the bundled placeholder)."""

    requires_auth = False
    url = f"{URL}/logo"
    name = "enhanced_login:logo"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get(self, request: web.Request) -> web.Response:
        return web.Response(
            body=self._settings.logo,
            content_type=self._settings.logo_type,
            headers={
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            },
        )


class FaviconView(HomeAssistantView):
    """Serves favicon.js with the logo and tile color filled in."""

    requires_auth = False
    url = f"{URL}/favicon.js"
    name = "enhanced_login:favicon"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get(self, request: web.Request) -> web.Response:
        return web.Response(
            text=self._settings.favicon_js,
            content_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )


def _is_readable(hass: HomeAssistant, path: Path) -> bool:
    """Files inside the configuration folder are fine (the YAML is admin-controlled).

    Home Assistant's allowlist by default only covers ``www`` and ``media``, so
    anything else outside the configuration folder must be allowlisted explicitly.
    """
    resolved = path.resolve()
    if resolved.is_relative_to(Path(hass.config.config_dir).resolve()):
        return True
    return bool(hass.config.is_allowed_path(str(resolved)))


def _load_settings(hass: HomeAssistant, conf: dict) -> Settings:
    """Read the logo and the template files (runs in the executor)."""
    settings = Settings()
    logo_conf = conf.get(CONF_LOGO)
    data = None
    if logo_conf:
        try:
            path = Path(hass.config.path(logo_conf))
            suffix = path.suffix.lower()
            if suffix not in _LOGO_TYPES:
                raise ValueError(f"unsupported file type {suffix or '(none)'}")
            if not _is_readable(hass, path):
                raise ValueError(
                    "path is outside the configuration folder and not allowed "
                    "(allowlist_external_dirs)"
                )
            if path.stat().st_size > _LOGO_MAX_BYTES:
                raise ValueError("file is larger than 2 MB")
            data = path.read_bytes()
            settings.logo_type = _LOGO_TYPES[suffix]
        except (OSError, ValueError) as err:
            _LOGGER.warning("Logo %s cannot be used (%s); using the placeholder", logo_conf, err)
            data = None
    if data is None:
        data = (STATIC_DIR / DEFAULT_LOGO).read_bytes()
        settings.logo_type = "image/png"
    settings.logo = data
    settings.logo_hash = hashlib.sha1(data).hexdigest()[:8]
    settings.tile = conf.get(CONF_TILE_COLOR) or DEFAULT_TILE
    # The placeholder logo must not replace the favicon unless asked for explicitly.
    settings.favicon = bool(conf.get(CONF_FAVICON, bool(logo_conf)))

    template = (STATIC_DIR / "favicon.js").read_text(encoding="utf-8")
    settings.favicon_js = template.replace(
        '"__LOGO__"', json.dumps(f"{URL}/logo?v={settings.logo_hash}")
    ).replace('"__BACKGROUND__"', json.dumps(settings.tile))

    digest = hashlib.sha1()
    for name in ASSETS:
        digest.update((STATIC_DIR / name).read_bytes())
    digest.update(settings.favicon_js.encode())
    digest.update(str(settings.favicon).encode())
    settings.version = digest.hexdigest()[:8]
    return settings


# ----------------------------------------------------------- Translation ----



def _ws(phrase: str) -> str:
    """Regex for a sentence in which whitespace may wrap arbitrarily."""
    return r"\s+".join(re.escape(part) for part in phrase.split())


_DE_PHRASES = {
    "OIDC Login - Home Assistant": "Anmelden – Home Assistant",
    "Done! - Home Assistant": "Fertig – Home Assistant",
    "Oops! - Home Assistant": "Fehler – Home Assistant",
    "Logged in! - Home Assistant": "Angemeldet – Home Assistant",
    "OIDC Redirect - Home Assistant": "Weiterleitung – Home Assistant",
    "Please login to Home Assistant on another device and enter this code when asked:": (
        "Melde dich auf einem anderen Gerät bei Home Assistant an und gib "
        "dort diesen Code ein, wenn danach gefragt wird:"
    ),
    "The login will continue automatically when you complete the login on your "
    "other device. Please keep the app open.": (
        "Die Anmeldung wird automatisch fortgesetzt, sobald du sie auf dem "
        "anderen Gerät abgeschlossen hast. Lass die App bitte geöffnet."
    ),
    "Or log in with": "oder",
    "Logged in!": "Angemeldet!",
    "Continue on this device": "Auf diesem Gerät fortfahren",
    "Tap Continue to login to Home Assistant on this device.": (
        "Tippe auf die Schaltfläche, um dich auf diesem Gerät bei "
        "Home Assistant anzumelden."
    ),
    "Use a code from another device": "Code von einem anderen Gerät verwenden",
    "On your other device, open the Home Assistant app. You will see a 6-digit code.": (
        "Öffne auf dem anderen Gerät die Home-Assistant-App. "
        "Dort wird ein 6-stelliger Code angezeigt."
    ),
    "Input that code here and click Approve to login on the other device.": (
        "Gib den Code hier ein und bestätige, um das andere Gerät anzumelden."
    ),
    "Approve login on the other device": "Anmeldung auf dem anderen Gerät bestätigen",
    "Login failed.": "Anmeldung fehlgeschlagen.",
    "Success!": "Geschafft!",
    "You have successfully logged in on your mobile device. It should continue "
    "the login soon.": (
        "Du bist auf deinem Mobilgerät angemeldet. Dort geht es gleich weiter."
    ),
    "You have been logged out on this device.": (
        "Auf diesem Gerät wurdest du wieder abgemeldet."
    ),
    "Redirecting...": "Weiterleitung …",
    # Error messages of the integration
    "Missing state cookie, please restart login.": (
        "Das Sitzungs-Cookie fehlt. Bitte die Anmeldung neu starten."
    ),
    "Invalid state, please restart login.": (
        "Ungültiger Sitzungsstatus. Bitte die Anmeldung neu starten."
    ),
    "Failed to link state to device code, please restart login.": (
        "Der Code konnte nicht zugeordnet werden. Bitte die Anmeldung neu starten."
    ),
    "Invalid redirect_uri, please restart login.": (
        "Ungültige Weiterleitungsadresse. Bitte die Anmeldung neu starten."
    ),
    "Failed to generate device code, please restart login.": (
        "Der Code konnte nicht erzeugt werden. Bitte die Anmeldung neu starten."
    ),
    "Missing code or state parameter.": "Code oder Status fehlen in der Antwort.",
    "State parameter does not match, possible CSRF attack.": (
        "Der Status stimmt nicht überein (möglicher CSRF-Angriff)."
    ),
    "Failed to get user details, see Home Assistant logs for more information.": (
        "Die Benutzerdaten konnten nicht abgerufen werden. "
        "Details stehen im Home-Assistant-Protokoll."
    ),
    "User is not in the correct group to access Home Assistant, contact your "
    "administrator!": (
        "Dein Konto ist nicht in der richtigen Gruppe für den Zugriff auf "
        "Home Assistant. Bitte wende dich an den Administrator."
    ),
    "Failed to save user information, session probably expired. Please sign in "
    "again.": (
        "Die Benutzerdaten konnten nicht gespeichert werden, die Sitzung ist "
        "vermutlich abgelaufen. Bitte erneut anmelden."
    ),
    "Integration is misconfigured, discovery could not be obtained.": (
        "Die Integration ist falsch konfiguriert (Discovery nicht abrufbar)."
    ),
}

_DE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_ws(src)), dst) for src, dst in _DE_PHRASES.items()
]
_DE_RULES += [
    (re.compile(r"Default\s+login\s+\(username\s+(?:&|&amp;)\s+password\)"), "Mit lokalem Konto anmelden"),
    (re.compile(r"Try\s+again"), "Erneut versuchen"),
    (re.compile(r">\s*Restart\s*</a>"), ">Neu starten</a>"),
    (re.compile(r"(\s)Help(\s*<!--\s*mdi)"), r"\1Hilfe\2"),
]

_TITLES = {
    "de": ("Willkommen zuhause!", "Melde dich an, um dein Zuhause zu steuern."),
    "en": ("Welcome home!", "Sign in to control your home."),
}

_LOGIN_BTN = re.compile(r"(<a\s+id=\"login-button\")([^>]*>)\s*Login\s+with\s+(.+?)\s*</a>", re.S)
_CARD_OPEN = '<div class="bg-card text-foreground border border-divider rounded-xl p-4">'


def _welcome_login(match: re.Match[str], lang: str) -> str:
    name = match.group(3)
    microsoft = "microsoft" in name.lower()
    attr = ' data-el="ms"' if microsoft else ""
    if lang == "de":
        label = "Mit Microsoft anmelden" if microsoft else f"Mit {name} anmelden"
    else:
        label = f"Sign in with {'Microsoft' if microsoft else name}"
    return f"{match.group(1)}{attr}{match.group(2)}{label}</a>"


def transform_oidc_page(html: str, lang: str) -> str:
    """Translate texts and add a heading to the welcome page."""
    html = _LOGIN_BTN.sub(lambda m: _welcome_login(m, lang), html)

    if lang == "de":
        for pattern, replacement in _DE_RULES:
            html = pattern.sub(replacement, html)
        html = html.replace('<html lang="en"', '<html lang="de"', 1)

    if 'id="login-button"' in html or 'id="alternative-sign-in-link"' in html:
        title, sub = _TITLES.get(lang, _TITLES["en"])
        head = f'<h1 class="el-title">{title}</h1>'
        if 'id="login-button"' in html:
            head += f'<p class="el-sub">{sub}</p>'
        html = html.replace(_CARD_OPEN, _CARD_OPEN + head, 1)
    return html



# ----------------------------------------------------------- Route wrapping ----

_SKIP_PREFIXES = ("/auth/oidc/static/", "/auth/oidc/device-sse")


def _is_target(path: str) -> bool:
    if path == "/auth/authorize":
        return True
    return path.startswith("/auth/oidc/") and not path.startswith(_SKIP_PREFIXES)


_ICON_TAGS = re.compile(
    r"<link[^>]+rel=[\"'](?:shortcut icon|icon|apple-touch-icon|mask-icon)[\"'][^>]*>", re.I
)


def _inject(html: str, settings: Settings) -> str:
    version = settings.version
    if settings.favicon:
        html = _ICON_TAGS.sub("", html)
    head = (
        f'<link rel="stylesheet" href="{URL}/theme.css">'
        f'<link rel="stylesheet" href="{URL}/login.css?v={version}">'
    )
    script = f'<script src="{URL}/login.js?v={version}" defer></script>'
    if settings.favicon:
        script += f'<script src="{URL}/favicon.js?v={version}" defer></script>'
    if "</head>" in html:
        html = html.replace("</head>", head + "</head>", 1)
    if "</body>" in html:
        html = html.replace("</body>", script + "</body>", 1)
    else:
        html += script
    return html


def _wrap(hass: HomeAssistant, handler, settings: Settings):
    """Wrap the handler of a sign-in route (fail-open)."""

    async def enhanced_login_handler(request: web.Request):
        response = await handler(request)
        try:
            if request.method not in ("GET", "POST") or request.query.get("el") == "0":
                return response
            return await _transform(hass, request, response, settings)
        except Exception:  # noqa: BLE001 - fail-open
            _LOGGER.exception("Could not enhance the sign-in page")
            return response

    enhanced_login_handler._el_patched = True  # type: ignore[attr-defined]
    return enhanced_login_handler


def _patch_routes(hass: HomeAssistant, settings: Settings) -> int:
    """Wrap all sign-in routes (/auth/authorize, /auth/oidc/*)."""
    patched = 0
    for resource in hass.http.app.router.resources():
        if not _is_target(resource.canonical):
            continue
        for route in resource:
            handler = getattr(route, "_handler", None)
            if handler is None or getattr(handler, "_el_patched", False):
                continue
            route._handler = _wrap(hass, handler, settings)
            patched += 1
    return patched


_NOTIFY_ID = "enhanced_login_inactive"

_INACTIVE = {
    "en": (
        "Enhanced Login is not active",
        "The enhanced sign-in design is not active. Signing in still works with "
        "the original design. A likely cause is an update of Home Assistant or "
        "hass-oidc-auth. Please check the `enhanced_login` integration and its "
        "release notes.",
    ),
    "de": (
        "Enhanced Login ist nicht aktiv",
        "Das erweiterte Anmeldedesign ist nicht aktiv. Die Anmeldung funktioniert "
        "weiterhin im Original-Design. Mögliche Ursache: ein Update von Home "
        "Assistant oder hass-oidc-auth. Bitte die Integration `enhanced_login` "
        "und ihre Release Notes prüfen.",
    ),
}


def _verify(hass: HomeAssistant) -> None:
    """Notify if /auth/authorize is not wrapped (for example after an update).

    Signing in stays possible with the original design.
    """
    try:
        from homeassistant.components import persistent_notification  # noqa: PLC0415

        active = False
        for resource in hass.http.app.router.resources():
            if resource.canonical != "/auth/authorize":
                continue
            for route in resource:
                if getattr(getattr(route, "_handler", None), "_el_patched", False):
                    active = True
        if active:
            persistent_notification.async_dismiss(hass, _NOTIFY_ID)
            return
        _LOGGER.warning("Enhanced Login: /auth/authorize could not be wrapped")
        lang = (hass.config.language or "en").split("-")[0].lower()
        title, message = _INACTIVE.get(lang, _INACTIVE["en"])
        persistent_notification.async_create(
            hass, message, title=title, notification_id=_NOTIFY_ID
        )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Enhanced Login: verification failed")


async def _transform(hass, request, response, settings: Settings):
    """Adapt an HTML response; return everything else unchanged."""
    if isinstance(response, web.FileResponse):
        # Original Home Assistant page (when hass-oidc-auth does not step in)
        path = getattr(response, "_path", None)
        if request.path != "/auth/authorize" or not path:
            return response
        html = await hass.async_add_executor_job(
            lambda: Path(path).read_text(encoding="utf-8")
        )
        if "</head>" not in html:
            return response
        return web.Response(
            text=_inject(html, settings),
            content_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    if not isinstance(response, web.Response) or response.content_type != "text/html":
        return response
    if response.headers.get("Content-Encoding"):
        return response

    html = response.text
    if not html or "</head>" not in html:
        return response

    if request.path.startswith("/auth/oidc/"):
        lang = (hass.config.language or "en").split("-")[0].lower()
        html = transform_oidc_page(html, lang)

    response.text = _inject(html, settings)
    response.headers.pop("Content-Length", None)
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------------------------------------------------------------- Setup ----


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Provide static files and theme CSS, wrap the sign-in routes."""
    conf = config.get(DOMAIN) or {}
    settings = await hass.async_add_executor_job(_load_settings, hass, conf)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(f"{URL}/{name}", str(STATIC_DIR / name), True)
            for name in ASSETS
        ]
    )
    hass.http.register_view(ThemeView(hass, settings))
    hass.http.register_view(LogoView(settings))

    if settings.favicon:
        hass.http.register_view(FaviconView(settings))
        # Favicon in the whole UI (the script is loaded on every frontend page)
        try:
            from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

            add_extra_js_url(hass, f"{URL}/favicon.js?v={settings.version}")
        except Exception:  # noqa: BLE001 - the favicon is optional
            _LOGGER.warning("Enhanced Login: could not register the favicon in the frontend")

    @callback
    def _apply(_event=None) -> None:
        try:
            count = _patch_routes(hass, settings)
        except Exception:  # noqa: BLE001 - never block the sign-in
            _LOGGER.exception("Enhanced Login: could not wrap the sign-in routes")
            return
        if count:
            _LOGGER.info(
                "Enhanced Login: %s sign-in routes wrapped (version %s)", count, settings.version
            )

    _apply()
    # More passes, in case routes are registered later
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _apply)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _apply)
    async_call_later(hass, 20, _apply)

    @callback
    def _check(_now=None) -> None:
        _verify(hass)

    # After startup, check that the sign-in page is really enhanced (for example after updates)
    async_call_later(hass, 90, _check)
    return True
