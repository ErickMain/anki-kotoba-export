"""Shared "push cards to Kotoba via the direct API" orchestration - create
vs. overwrite, and the stale-link fallback - used by both the interactive
preview dialog's Upload button and unattended automatic exports, so the two
paths can't drift apart.
"""
from . import api as kotoba_api
from . import format as kotoba_format


def upload_deck(cookie: str, preset, cards: list, deck_name: str, max_retries: int = kotoba_api.MAX_RETRIES) -> dict:
    """Creates or overwrites (per preset.deck_reuse_mode) a Kotoba deck for
    `deck_name`. Mutates preset.deck_links in place on success - callers are
    responsible for persisting the preset afterward. Raises
    kotoba_api.KotobaApiError on failure; callers decide how to surface or
    log that (a dialog for interactive use, a history entry for automatic).

    max_retries is forwarded to the underlying API calls - unattended
    callers (__init__.py's automatic export) pass a smaller budget than the
    interactive default, since retries add bounded but real delay and this
    can run during Anki's own startup/shutdown/sync.
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
                max_retries=max_retries,
            )
            preset.set_deck_link(deck_name, link["id"], resp["readwrite_secret"])
            return {"id": link["id"]}
        except kotoba_api.KotobaApiError as exc:
            # Only a stale link (deck deleted, or the stored secret no
            # longer matches) should fall through to creating a fresh deck.
            # Anything else - e.g. a 400 validation rejection like "duplicate
            # question found" - must propagate, or it would silently succeed
            # against a brand-new deck instead of surfacing the real error,
            # silently rebinding the preset to that new deck in the process.
            if exc.status_code not in (403, 404):
                raise

    resp = kotoba_api.create_deck(
        cookie, deck_name, short_name, cards, description=preset.deck_description, max_retries=max_retries
    )
    if overwrite:
        preset.set_deck_link(deck_name, resp["id"], resp["readwrite_secret"])
    return {"id": resp["id"]}
