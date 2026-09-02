from kotoba import api, upload
from kotoba.presets import Preset


def _preset(reuse_mode="new_each_time"):
    p = Preset.new("Test preset")
    p.deck_reuse_mode = reuse_mode
    return p


def test_upload_deck_creates_when_new_each_time(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api,
        "create_deck",
        lambda *a, **kw: calls.append(("create", a, kw)) or {"id": "new-id", "readwrite_secret": "s"},
    )

    preset = _preset("new_each_time")
    result = upload.upload_deck("cookie", preset, [], "My Deck")

    assert result == {"id": "new-id"}
    assert calls[0][0] == "create"
    # new_each_time never records a link, even after a successful create.
    assert preset.get_deck_link("My Deck") is None


def test_upload_deck_creates_and_links_when_overwrite_has_no_existing_link(monkeypatch):
    monkeypatch.setattr(api, "create_deck", lambda *a, **kw: {"id": "new-id", "readwrite_secret": "s"})

    preset = _preset("overwrite")
    upload.upload_deck("cookie", preset, [], "My Deck")

    assert preset.get_deck_link("My Deck") == {"id": "new-id", "secret": "s"}


def test_upload_deck_patches_when_overwrite_has_an_existing_link(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api,
        "update_deck",
        lambda *a, **kw: calls.append(("update", a, kw)) or {"readwrite_secret": "new-secret"},
    )
    monkeypatch.setattr(api, "create_deck", lambda *a, **kw: calls.append(("create", a, kw)))

    preset = _preset("overwrite")
    preset.set_deck_link("My Deck", "existing-id", "old-secret")

    result = upload.upload_deck("cookie", preset, [], "My Deck")

    assert result == {"id": "existing-id"}
    assert [c[0] for c in calls] == ["update"]  # create was never called
    assert preset.get_deck_link("My Deck") == {"id": "existing-id", "secret": "new-secret"}


def test_upload_deck_falls_back_to_create_when_link_is_stale(monkeypatch):
    def fake_update(*a, **kw):
        raise api.KotobaApiError("deck not found", status_code=404)

    monkeypatch.setattr(api, "update_deck", fake_update)
    monkeypatch.setattr(api, "create_deck", lambda *a, **kw: {"id": "fresh-id", "readwrite_secret": "fresh-secret"})

    preset = _preset("overwrite")
    preset.set_deck_link("My Deck", "stale-id", "stale-secret")

    result = upload.upload_deck("cookie", preset, [], "My Deck")

    assert result == {"id": "fresh-id"}
    assert preset.get_deck_link("My Deck") == {"id": "fresh-id", "secret": "fresh-secret"}


def test_upload_deck_propagates_error_when_create_fails(monkeypatch):
    def fake_create(*a, **kw):
        raise api.KotobaApiError("bad request", status_code=400)

    monkeypatch.setattr(api, "create_deck", fake_create)

    preset = _preset("new_each_time")
    try:
        upload.upload_deck("cookie", preset, [], "My Deck")
        assert False, "expected KotobaApiError"
    except api.KotobaApiError:
        pass


def test_upload_deck_different_names_get_independent_links(monkeypatch):
    ids = iter(["id-1", "id-2"])
    monkeypatch.setattr(
        api, "create_deck", lambda *a, **kw: {"id": next(ids), "readwrite_secret": "s"}
    )

    preset = _preset("overwrite")
    upload.upload_deck("cookie", preset, [], "Deck A")
    upload.upload_deck("cookie", preset, [], "Deck B")

    assert preset.get_deck_link("Deck A")["id"] == "id-1"
    assert preset.get_deck_link("Deck B")["id"] == "id-2"
