"""Guards the Microsoft button styling against localized hass-oidc-auth texts."""

from __future__ import annotations

from pathlib import Path

import custom_components.enhanced_login as el

STATIC = Path(el.__file__).parent / "static"


def test_script_marks_localized_login_button_as_microsoft():
    js = (STATIC / "login.js").read_text(encoding="utf-8")
    assert 'getElementById("login-button")' in js
    assert 'setAttribute("data-el", "ms")' in js
    assert "microsoft|entra" in js


def test_stylesheet_styles_the_marked_button():
    css = (STATIC / "login.css").read_text(encoding="utf-8")
    assert '#login-button[data-el="ms"]' in css


def test_already_localized_page_is_not_broken():
    html = (
        '<html lang="de"><head></head><body>'
        '<div class="bg-card text-foreground border border-divider rounded-xl p-4">'
        '<a id="login-button" class="x">Mit Microsoft Entra ID anmelden</a>'
        "</div></body></html>"
    )
    out = el.transform_oidc_page(html, "de")
    assert "Mit Microsoft Entra ID anmelden" in out
    assert "Willkommen zuhause!" in out
