"""Central place to read/write the addon's config, so GUI submodules don't
each have to know the addon's package name for aqt.addonManager calls.
"""
from aqt import mw

# __name__ here is "<addon_package>.config_store" - the first segment is
# always the addon's package name, regardless of which module imports us.
ADDON_PACKAGE = __name__.split(".")[0]


def get_config() -> dict:
    return mw.addonManager.getConfig(ADDON_PACKAGE) or {}


def save_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(ADDON_PACKAGE, cfg)
