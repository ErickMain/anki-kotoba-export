from kotoba import api


class FakeResponse:
    def __init__(self, json_data=None, text="", raises=False, status_code=200, headers=None):
        self._json_data = json_data
        self.text = text
        self._raises = raises
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = headers or {}

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._json_data


def test_normalize_cookie_header_passes_through_well_formed_header():
    raw = "connect.sid=s%3AoAOLHD7qq8ME.sig; other=value"
    assert api.normalize_cookie_header(raw) == raw


def test_normalize_cookie_header_wraps_bare_value_as_connect_sid():
    raw = "s:oAOLHD7qq8ME02fUjYHyFZi_wk2-OpXLoac2owsM/2hsORVheByJrDsGhkqhfaFzdKAWky0fSHQ"
    assert api.normalize_cookie_header(raw) == f"connect.sid={raw}"


def test_normalize_cookie_header_strips_whitespace():
    assert api.normalize_cookie_header("  connect.sid=abc  ") == "connect.sid=abc"


def test_normalize_cookie_header_empty():
    assert api.normalize_cookie_header("") == ""


def test_extract_error_detail_prefers_kotoba_rejection_reason():
    resp = FakeResponse(
        json_data={
            "success": False,
            "errorType": "deck_validation",
            "rejectionReason": "Duplicate question found",
            "rejectedLine": 3,
        }
    )
    detail = api._extract_error_detail(resp)
    assert "Duplicate question found" in detail
    assert "3" in detail


def test_extract_error_detail_falls_back_to_message():
    resp = FakeResponse(json_data={"message": "Not logged in"})
    assert api._extract_error_detail(resp) == "Not logged in"


def test_extract_error_detail_falls_back_to_errors_array():
    resp = FakeResponse(json_data={"errors": [{"msg": "bad name"}, "other issue"]})
    assert api._extract_error_detail(resp) == "bad name; other issue"


def test_extract_error_detail_falls_back_to_raw_text_when_not_json():
    resp = FakeResponse(text="<html>502 Bad Gateway</html>", raises=True)
    assert "502 Bad Gateway" in api._extract_error_detail(resp)


def test_list_my_decks_hits_the_right_endpoint_and_returns_json(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse(json_data=[{"_id": "1", "name": "Deck A"}])

    monkeypatch.setattr(api.requests, "get", fake_get)

    decks = api.list_my_decks("connect.sid=abc")

    assert captured["url"] == f"{api.BASE_URL}/users/me/decks"
    assert captured["headers"]["Cookie"] == "connect.sid=abc"
    assert decks == [{"_id": "1", "name": "Deck A"}]


def test_list_my_decks_raises_on_error_response(monkeypatch):
    monkeypatch.setattr(
        api.requests, "get", lambda *a, **kw: FakeResponse(json_data={"message": "nope"}, status_code=500)
    )
    try:
        api.list_my_decks("connect.sid=abc")
        assert False, "expected KotobaApiError"
    except api.KotobaApiError as exc:
        assert "nope" in str(exc)


def test_delete_deck_hits_the_right_endpoint(monkeypatch):
    captured = {}

    def fake_delete(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResponse(status_code=200)

    monkeypatch.setattr(api.requests, "delete", fake_delete)

    api.delete_deck("connect.sid=abc", "deck123")

    assert captured["url"] == f"{api.BASE_URL}/decks/deck123"
