"""Tests for the pure logic of Enhanced Login."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web
import pytest
import voluptuous as vol

import custom_components.enhanced_login as el


class FakeConfig:
    language = "de"

    def __init__(self, base: Path):
        self._base = base
        self.config_dir = str(base)
        # Like Home Assistant: only www and media are allowed by default,
        # the configuration folder itself is not.
        self.allowed = [str(base / "www"), str(base / "media")]

    def path(self, *parts: str) -> str:
        return str(self._base.joinpath(*parts))

    def is_allowed_path(self, path: str) -> bool:
        return any(str(path).startswith(a) for a in self.allowed)


class FakeHass:
    def __init__(self, base: Path, data=None):
        self.config = FakeConfig(base)
        self.data = data or {}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


# ------------------------------------------------------------- config ------


def test_config_schema_accepts_bare_and_full():
    assert el.CONFIG_SCHEMA({"enhanced_login": None})
    assert el.CONFIG_SCHEMA(
        {"enhanced_login": {"logo": "www/x.png", "tile_color": "#112233", "favicon": True}}
    )


@pytest.mark.parametrize("bad", ["red", "#12", "#GGGGGG", "112233"])
def test_config_schema_rejects_bad_tile_color(bad):
    with pytest.raises(vol.Invalid):
        el.CONFIG_SCHEMA({"enhanced_login": {"tile_color": bad}})


# ------------------------------------------------------------- settings ----


def test_default_settings_use_placeholder_and_no_favicon(tmp_path):
    settings = el._load_settings(FakeHass(tmp_path), {})
    assert settings.logo.startswith(b"\x89PNG")
    assert settings.tile == el.DEFAULT_TILE
    assert settings.favicon is False
    assert "__LOGO__" not in settings.favicon_js


def test_custom_logo_enables_favicon_by_default(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    settings = el._load_settings(FakeHass(tmp_path), {"logo": "logo.png", "tile_color": "#000"})
    assert settings.logo.endswith(b"fake")
    assert settings.favicon is True
    assert settings.tile == "#000"
    assert f"/enhanced-login/logo?v={settings.logo_hash}" in settings.favicon_js
    assert '"#000"' in settings.favicon_js


def test_favicon_can_be_disabled_explicitly(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    settings = el._load_settings(FakeHass(tmp_path), {"logo": "logo.png", "favicon": False})
    assert settings.favicon is False


@pytest.mark.parametrize("name", ["missing.png", "logo.exe"])
def test_invalid_logo_falls_back_to_placeholder(tmp_path, name):
    (tmp_path / "logo.exe").write_bytes(b"x")
    settings = el._load_settings(FakeHass(tmp_path), {"logo": name})
    assert settings.logo.startswith(b"\x89PNG") and len(settings.logo) > 1000


def test_logo_outside_allowed_paths_is_rejected(tmp_path):
    base = tmp_path / "config"
    base.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"\x89PNG-outside")
    settings = el._load_settings(FakeHass(base), {"logo": str(outside)})
    assert b"outside" not in settings.logo


def test_logo_in_config_root_is_accepted(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG-root")
    settings = el._load_settings(FakeHass(tmp_path), {"logo": "logo.png"})
    assert settings.logo.endswith(b"root")


def test_logo_in_www_is_accepted(tmp_path):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "logo.png").write_bytes(b"\x89PNG-www")
    settings = el._load_settings(FakeHass(tmp_path), {"logo": "www/logo.png"})
    assert settings.logo.endswith(b"www")


def test_logo_in_allowlisted_external_dir_is_accepted(tmp_path):
    base = tmp_path / "config"
    base.mkdir()
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "logo.png").write_bytes(b"\x89PNG-ext")
    hass = FakeHass(base)
    hass.config.allowed.append(str(ext))
    settings = el._load_settings(hass, {"logo": str(ext / "logo.png")})
    assert settings.logo.endswith(b"ext")


# ---------------------------------------------------------------- theme ----


def test_theme_tokens_from_theme_and_fallback():
    theme = {
        "primary-color": "#ff0000",
        "modes": {"dark": {"primary-color": "#00ff00", "el-page-bg": "#010203"}},
    }
    light = el._tokens(theme, "light")
    dark = el._tokens(theme, "dark")
    assert light["accent"] == "#ff0000"
    assert dark["accent"] == "#00ff00"
    assert dark["bg"] == "#010203"
    assert light["bg"] == el.FALLBACK["light"]["bg"]


def test_legacy_dl_tokens_still_work():
    assert el._tokens({"dl-page-bg": "#abcdef"}, "light")["bg"] == "#abcdef"


@pytest.mark.parametrize(
    "value", ["url(http://evil)", "red; } body{", "@import x", "expression(1)", 5, None]
)
def test_unsafe_theme_values_are_ignored(value):
    assert el._tokens({"primary-color": value}, "light")["accent"] == el.FALLBACK["light"]["accent"]


def test_theme_css_contains_both_modes_tile_and_logo(tmp_path):
    settings = el._load_settings(FakeHass(tmp_path), {"tile_color": "#123456"})
    hass = FakeHass(tmp_path, {"frontend_themes": {"t": {"primary-color": "#112233"}}, "frontend_default_theme": "t"})
    css = el.build_theme_css(hass, settings)
    assert "--el-accent:#112233" in css
    assert "prefers-color-scheme: dark" in css
    assert css.count("--el-tile:#123456") == 2
    assert f"url(/enhanced-login/logo?v={settings.logo_hash})" in css


# ----------------------------------------------------------- translation ---


WELCOME = (
    "<html lang=\"en\"><head></head><body>"
    '<div class="bg-card text-foreground border border-divider rounded-xl p-4">'
    '<a id="login-button" class="x">Login with Microsoft</a>'
    "<p>Or log in with</p>"
    "<a>Default login (username &amp; password)</a></div></body></html>"
)


def test_transform_welcome_german():
    out = el.transform_oidc_page(WELCOME, "de")
    assert "Mit Microsoft anmelden" in out
    assert 'data-el="ms"' in out
    assert "Mit lokalem Konto anmelden" in out
    assert "Willkommen zuhause!" in out
    assert '<html lang="de"' in out


def test_transform_welcome_english_keeps_text():
    out = el.transform_oidc_page(WELCOME, "en")
    assert "Sign in with Microsoft" in out
    assert "Welcome home!" in out
    assert "Mit lokalem" not in out


def test_inject_adds_assets_and_strips_icons_only_with_favicon():
    page = '<html><head><link rel="icon" href="/x.ico"></head><body></body></html>'
    plain = el._inject(page, el.Settings(version="v1", favicon=False))
    assert '/enhanced-login/login.css?v=v1' in plain and "favicon.js" not in plain
    assert 'rel="icon"' in plain
    full = el._inject(page, el.Settings(version="v1", favicon=True))
    assert "favicon.js?v=v1" in full and 'href="/x.ico"' not in full


def test_particles_only_injected_on_oidc_pages():
    page = "<html><head></head><body></body></html>"
    settings = el.Settings(version="v1")
    assert "particles.js" in el._inject(page, settings, "/auth/oidc/welcome")
    # the stock sign-in page draws its own particles
    assert "particles.js" not in el._inject(page, settings, "/auth/authorize")


# -------------------------------------------------------- route wrapping ---


def test_is_target():
    assert el._is_target("/auth/authorize")
    assert el._is_target("/auth/oidc/welcome")
    assert not el._is_target("/auth/oidc/static/app.js")
    assert not el._is_target("/auth/oidc/device-sse")
    assert not el._is_target("/api/states")


def _wrapped(handler, settings=None):
    hass = FakeHass(Path("."))
    return el._wrap(hass, handler, settings or el.Settings(version="v1"))


def _request(path="/auth/oidc/welcome", method="GET", query=None):
    return SimpleNamespace(path=path, method=method, query=query or {})


def test_wrapper_transforms_html():
    async def handler(request):
        return web.Response(text=WELCOME, content_type="text/html")

    response = asyncio.run(_wrapped(handler)(_request()))
    assert "login.css" in response.text
    assert response.headers["Cache-Control"] == "no-cache"


def test_wrapper_skips_with_el0_and_other_methods():
    async def handler(request):
        return web.Response(text=WELCOME, content_type="text/html")

    assert "login.css" not in asyncio.run(_wrapped(handler)(_request(query={"el": "0"}))).text
    assert "login.css" not in asyncio.run(_wrapped(handler)(_request(method="DELETE"))).text


def test_wrapper_is_fail_open():
    sentinel = web.Response(text="<html><head></head></html>", content_type="text/html")

    async def handler(request):
        return sentinel

    wrapped = _wrapped(handler)
    original_inject = el._inject
    el._inject = lambda *a, **k: 1 / 0
    try:
        assert asyncio.run(wrapped(_request())) is sentinel
    finally:
        el._inject = original_inject


def test_wrapper_leaves_non_html_alone():
    response = web.json_response({"ok": True})

    async def handler(request):
        return response

    assert asyncio.run(_wrapped(handler)(_request())) is response


def test_patch_routes_is_idempotent():
    async def handler(request):
        return web.Response(text="x")

    route = SimpleNamespace(_handler=handler)
    resource = type("R", (), {"canonical": "/auth/authorize", "__iter__": lambda self: iter([route])})()
    other = type("R", (), {"canonical": "/api/x", "__iter__": lambda self: iter([SimpleNamespace(_handler=handler)])})()
    hass = SimpleNamespace(http=SimpleNamespace(app=SimpleNamespace(router=SimpleNamespace(resources=lambda: [resource, other]))))
    settings = el.Settings(version="v1")
    assert el._patch_routes(hass, settings) == 1
    assert el._patch_routes(hass, settings) == 0
    assert route._handler._el_patched is True


# ------------------------------------------------------------ static files --


def test_classes_used_by_scripts_exist_in_the_stylesheet():
    """Guards against renamed-but-not-updated class names between JS and CSS."""
    static = Path(el.__file__).parent / "static"
    css = (static / "login.css").read_text(encoding="utf-8")
    used = set()
    for name in ("login.js", "favicon.js", "particles.js"):
        text = (static / name).read_text(encoding="utf-8")
        used |= set(re.findall(r"""["'.](el-[a-z-]+)["']?""", text))
    used.discard("el-accent")  # CSS custom property, read via getPropertyValue("--el-accent")
    assert used, "expected the scripts to reference el- classes"
    for cls in sorted(used):
        assert f".{cls}" in css, f"{cls} is used in a script but not defined in login.css"


def test_injected_class_names_exist_in_the_stylesheet():
    css = (Path(el.__file__).parent / "static" / "login.css").read_text(encoding="utf-8")
    source = Path(el.__file__).read_text(encoding="utf-8")
    for cls in set(re.findall(r'class=\\?"(el-[a-z-]+)', source)):
        assert f".{cls}" in css, cls
    assert '[data-el="ms"]' in css


def test_no_leftover_legacy_prefix_in_static_files():
    static = Path(el.__file__).parent / "static"
    for name in ("login.css", "login.js", "favicon.js", "particles.js"):
        text = (static / name).read_text(encoding="utf-8")
        assert not re.search(r"\bdl-|data-dl|--dl-", text), f"legacy dl- prefix left in {name}"
