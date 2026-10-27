"""Light-weight stubs of the Home Assistant modules used by the integration.

The tests exercise the pure logic (theme tokens, translation, injection, route
wrapping) without installing Home Assistant itself.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import voluptuous as vol

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


class HomeAssistantView:  # minimal stand-in
    requires_auth = True
    url = ""
    name = ""


class StaticPathConfig:
    def __init__(self, url_path, path, cache_headers=True):
        self.url_path, self.path, self.cache_headers = url_path, path, cache_headers


_module("homeassistant")
_module("homeassistant.helpers")
_module("homeassistant.components")
_module(
    "homeassistant.helpers.config_validation",
    string=vol.Coerce(str),
    boolean=vol.Boolean(),
)
sys.modules["homeassistant.helpers"].config_validation = sys.modules[
    "homeassistant.helpers.config_validation"
]
_module(
    "homeassistant.components.http",
    HomeAssistantView=HomeAssistantView,
    StaticPathConfig=StaticPathConfig,
)
_module(
    "homeassistant.const",
    EVENT_HOMEASSISTANT_START="homeassistant_start",
    EVENT_HOMEASSISTANT_STARTED="homeassistant_started",
)
_module("homeassistant.helpers.event", async_call_later=lambda *a, **k: None)
_module("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
_module("homeassistant.helpers.typing", ConfigType=dict)
