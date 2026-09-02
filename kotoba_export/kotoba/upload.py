"""Shared "push cards to Kotoba via the direct API" orchestration - create
vs. overwrite, and the stale-link fallback - used by both the interactive
preview dialog's Upload button and unattended automatic exports, so the two
paths can't drift apart.
"""
from . import api as kotoba_api
from . import format as kotoba_format


def upload_deck(cookie: str, preset, cards: list, deck_name: str) -> dict:
    """Creates or overwrites (per preset.deck_reuse_mode) a Kotoba deck for
    `deck_name`. Mutates preset.deck_links in place on success - callers are
    responsible for persisting the preset afterward. Raises
    kotoba_api.KotobaApiError on failure; callers decide how to surface or
    log that (a dialog for interactive use, a history entry for automatic).
    """
    short_name = kotoba_format.make_short_name(deck_name)
    overwrite = preset.deck_reuse_mode == "overwrite"
    link = preset.get_deck_link(deck_name) if overwrite else None

    if link:
        try:
            resp = kotoba_api.update_deck(
                cookie,
                link["id"],
                link["secret"],
                deck_name,
                short_name,
                cards,
                description=preset.deck_description,
            )
            preset.set_deck_link(deck_name, link["id"], resp["readwrite_secret"])
            return {"id": link["id"]}
        except kotoba_api.KotobaApiError:
            # Stale link (deck deleted / secret rotated on Kotoba's side) -
            # fall through to creating a fresh deck under this same name.
            pass

    resp = kotoba_api.create_deck(
        cookie, deck_name, short_name, cards, description=preset.deck_description
    )
    if overwrite:
        preset.set_deck_link(deck_name, resp["id"], resp["readwrite_secret"])
    return {"id": resp["id"]}
