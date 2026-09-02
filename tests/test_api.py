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


def test_normalize_cookie_header_rejects_embedded_crlf():
    # Passing this straight to `requests` would raise InvalidHeader with the
    # raw cookie value embedded in its message - reject it here first, with
    # a static message, so a malformed cookie can never leak into a
    # displayed/logged error.
    try:
        api.normalize_cookie_header("connect.sid=abc\r\nX-Injected: evil")
        assert False, "expected KotobaApiError"
    except api.KotobaApiError as exc:
        assert "abc" not in str(exc)
        assert "Injected" not in str(exc)


def test_normalize_cookie_header_rejects_embedded_bare_newline():
    try:
        api.normalize_cookie_header("connect.sid=abc\nX-Injected: evil")
        assert False, "expected KotobaApiError"
    except api.KotobaApiError:
        pass


def test_headers_surfaces_crlf_cookie_as_kotoba_api_error(monkeypatch):
    # End-to-end: a malformed cookie must never reach requests.* at all.
    called = []
    monkeypatch.setattr(api.requests, "get", lambda *a, **kw: called.append(1))

    try:
        api.list_my_decks("connect.sid=abc\r\nX-Injected: evil")
        assert False, "expected KotobaApiError"
    except api.KotobaApiError:
        pass
    assert called == []


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


# -- retry/backoff -----------------------------------------------------


def _no_sleep(monkeypatch, record=None):
    """Replaces api.time.sleep with a fast no-op, optionally recording the
    requested delays so tests don't actually wait."""
    def fake_sleep(seconds):
        if record is not None:
            record.append(seconds)

    monkeypatch.setattr(api.time, "sleep", fake_sleep)


def test_retry_delay_uses_retry_after_header_when_present():
    resp = FakeResponse(status_code=429, headers={"Retry-After": "3"})
    assert api._retry_delay(0, resp) == 3.0


def test_retry_delay_caps_retry_after_at_max_wait():
    resp = FakeResponse(status_code=429, headers={"Retry-After": "60"})
    assert api._retry_delay(0, resp) == api.MAX_RETRY_WAIT_SECONDS


def test_retry_delay_ignores_non_numeric_retry_after():
    resp = FakeResponse(status_code=429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    # Falls back to the exponential schedule rather than parsing a date.
    assert api._retry_delay(0, resp) == api.BASE_RETRY_DELAY_SECONDS


def test_retry_delay_falls_back_to_exponential_backoff_without_retry_after():
    resp = FakeResponse(status_code=502)
    assert api._retry_delay(0, resp) == api.BASE_RETRY_DELAY_SECONDS
    assert api._retry_delay(1, resp) == api.BASE_RETRY_DELAY_SECONDS * 2
    assert api._retry_delay(5, resp) == api.MAX_RETRY_WAIT_SECONDS  # capped


def test_retry_delay_exponential_with_no_response_at_all():
    assert api._retry_delay(0, None) == api.BASE_RETRY_DELAY_SECONDS


def test_send_with_retry_returns_immediately_on_success(monkeypatch):
    _no_sleep(monkeypatch)
    calls = []

    def send():
        calls.append(1)
        return FakeResponse(status_code=200)

    resp = api._send_with_retry(send)
    assert resp.status_code == 200
    assert len(calls) == 1


def test_send_with_retry_does_not_retry_non_retryable_status(monkeypatch):
    sleeps = []
    _no_sleep(monkeypatch, sleeps)
    calls = []

    def send():
        calls.append(1)
        return FakeResponse(status_code=400)

    resp = api._send_with_retry(send)
    assert resp.status_code == 400
    assert len(calls) == 1
    assert sleeps == []


def test_send_with_retry_retries_on_429_then_succeeds(monkeypatch):
    sleeps = []
    _no_sleep(monkeypatch, sleeps)
    responses = [FakeResponse(status_code=429, headers={"Retry-After": "1"}), FakeResponse(status_code=200)]

    def send():
        return responses.pop(0)

    resp = api._send_with_retry(send)
    assert resp.status_code == 200
    assert sleeps == [1.0]


def test_send_with_retry_gives_up_after_max_retries(monkeypatch):
    sleeps = []
    _no_sleep(monkeypatch, sleeps)
    calls = []

    def send():
        calls.append(1)
        return FakeResponse(status_code=429, headers={})

    resp = api._send_with_retry(send, max_retries=2)
    assert resp.status_code == 429  # left for the caller's _raise_for_response to handle
    assert len(calls) == 3  # initial attempt + 2 retries
    assert len(sleeps) == 2


def test_send_with_retry_retries_on_connection_error_then_succeeds(monkeypatch):
    _no_sleep(monkeypatch)
    attempts = {"n": 0}

    def send():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise api.requests.RequestException("connection reset")
        return FakeResponse(status_code=200)

    resp = api._send_with_retry(send)
    assert resp.status_code == 200
    assert attempts["n"] == 2


def test_send_with_retry_raises_after_max_retries_on_connection_error(monkeypatch):
    _no_sleep(monkeypatch)

    def send():
        raise api.requests.RequestException("connection reset")

    try:
        api._send_with_retry(send, max_retries=1)
        assert False, "expected KotobaApiError"
    except api.KotobaApiError as exc:
        assert "connection reset" in str(exc)


def test_send_with_retry_respects_zero_max_retries(monkeypatch):
    sleeps = []
    _no_sleep(monkeypatch, sleeps)
    calls = []

    def send():
        calls.append(1)
        return FakeResponse(status_code=429)

    resp = api._send_with_retry(send, max_retries=0)
    assert resp.status_code == 429
    assert len(calls) == 1
    assert sleeps == []


def test_create_deck_retries_on_429(monkeypatch):
    _no_sleep(monkeypatch)
    responses = [
        FakeResponse(status_code=429, headers={"Retry-After": "0"}),
        FakeResponse(json_data={"_id": "new-id"}, headers={api.RESPONSE_READWRITE_SECRET_HEADER: "secret"}),
    ]
    monkeypatch.setattr(api.requests, "post", lambda *a, **kw: responses.pop(0))

    result = api.create_deck("connect.sid=abc", "My Deck", "my_deck", [])

    assert result == {"id": "new-id", "readwrite_secret": "secret"}


def test_update_deck_retries_on_503(monkeypatch):
    _no_sleep(monkeypatch)
    responses = [
        FakeResponse(status_code=503),
        FakeResponse(headers={api.RESPONSE_READWRITE_SECRET_HEADER: "new-secret"}),
    ]
    monkeypatch.setattr(api.requests, "patch", lambda *a, **kw: responses.pop(0))

    result = api.update_deck("connect.sid=abc", "deck-id", "old-secret", "My Deck", "my_deck", [])

    assert result == {"readwrite_secret": "new-secret"}
