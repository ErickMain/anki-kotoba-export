"""Optional, opt-in direct upload to kotobaweb.com's internal deck API.

This is not a public/documented API. It authenticates the same way the
website does: a browser session cookie, which the user copies out of their
own DevTools once and pastes into the addon's settings. There is no API key
because Kotoba itself doesn't have one - see mistval/kotoba on GitHub
(api/auth/check_auth.js uses Passport's req.isAuthenticated(), backed by
Discord OAuth2 + an Express session cookie).

Header names and field limits below are taken verbatim from that project's
common/deck_permissions.js and common/deck_validation.js (checked
2026-09-01). If Kotoba changes its site, this module is what breaks - the
clipboard/CSV flow in format.py does not depend on any of this.
"""
import time

import requests

BASE_URL = "https://kotobaweb.com/api"
REQUEST_SECRET_HEADER = "Deck-Permissions-Secret"
RESPONSE_READWRITE_SECRET_HEADER = "Deck-Read-Write-Secret"
RESPONSE_PERMISSIONS_HEADER = "Deck-Permissions"

TIMEOUT_SECONDS = 15

# Kotoba rate-limits POST/PATCH deck routes (postPatchLimiter in its own
# source) - a "run all" or automatic export can now plausibly fire enough
# uploads back to back to hit that. Retries are deliberately conservative:
# few attempts, short capped waits. This can run unattended during Anki's
# own startup/shutdown/sync, where a long block is worse than a failed
# upload that gets logged to history and can just be retried next time -
# callers running unattended (see kotoba/upload.py, __init__.py) pass a
# smaller max_retries than this interactive default.
MAX_RETRIES = 2
BASE_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_WAIT_SECONDS = 8.0
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class KotobaApiError(Exception):
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


def normalize_cookie_header(raw: str) -> str:
    """Accepts either the full `Cookie:` request header (`name=value; ...`)
    or, forgivingly, a bare value copied from DevTools' parsed cookie table
    (which shows name and value in separate columns, so it's easy to only
    grab the value). A bare value has no `=` in it, so we assume it's
    `connect.sid`, Express-session's default cookie name and the one
    Kotoba's own login actually uses.

    Raises KotobaApiError (not a generic ValueError - callers already know
    how to surface that type) if the value contains a line break: passing
    that straight to `requests` raises InvalidHeader with the raw header
    text embedded in its message, which would otherwise leak the cookie
    into a logged/displayed error. Rejecting it here, before any request is
    attempted, also avoids wasting retries on what is always a permanent,
    not transient, failure.
    """
    raw = raw.strip()
    if "\r" in raw or "\n" in raw:
        raise KotobaApiError(
            "The session cookie contains a line break, which isn't valid in a Cookie header. "
            "Copy it fresh from DevTools' Headers tab (not the Cookies table) and try again."
        )
    if raw and "=" not in raw:
        return f"connect.sid={raw}"
    return raw


_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _headers(cookie_header: str, extra: dict = None) -> dict:
    headers = {
        "Cookie": normalize_cookie_header(cookie_header),
        "Content-Type": "application/json",
        # A plain "python-requests/x.y" UA gets blocked by some hosts' WAF
        # before the request even reaches Kotoba's own auth check.
        "User-Agent": _BROWSER_USER_AGENT,
    }
    if extra:
        headers.update(extra)
    return headers


def _extract_error_detail(resp) -> str:
    """Kotoba's deck validation (common/deck_validation.js) responds with
    {success: false, rejectionReason, rejectedLine, rejectedCard, ...} on a
    400, not a generic {"message": ...} - so that's the field worth
    surfacing first. Other endpoints may use "message"/"error"/"errors"
    instead, so those are tried too before falling back to raw text.
    """
    try:
        data = resp.json()
    except ValueError:
        return resp.text[:300].strip()

    if isinstance(data, dict):
        if data.get("rejectionReason"):
            detail = str(data["rejectionReason"])
            if data.get("rejectedLine") is not None:
                detail += f" (card #{data['rejectedLine']})"
            return detail
        if data.get("message"):
            return str(data["message"])
        if data.get("error"):
            return str(data["error"])
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            parts = [
                str(e.get("msg") or e.get("message") or e) if isinstance(e, dict) else str(e)
                for e in errors
            ]
            return "; ".join(parts)
        return str(data)[:300]
    return str(data)[:300]


def _retry_delay(attempt: int, resp) -> float:
    """attempt: 0-based count of retries already made (0 = about to make
    the first retry). Prefers a 429's Retry-After header when it's a plain
    integer-seconds value (an HTTP-date value falls back to the exponential
    schedule instead of parsing dates) over guessing, but never waits past
    MAX_RETRY_WAIT_SECONDS regardless of what the server asked for - a
    server asking for a long cooldown just means the retry likely fails
    again and the normal error path takes over, not that this should block
    for as long as the server would like.
    """
    if resp is not None and resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            return min(float(retry_after), MAX_RETRY_WAIT_SECONDS)
    return min(BASE_RETRY_DELAY_SECONDS * (2**attempt), MAX_RETRY_WAIT_SECONDS)


def _send_with_retry(send, max_retries: int = MAX_RETRIES):
    """Calls `send()` (a zero-arg callable performing one HTTP request),
    retrying with backoff on a 429/502/503/504 or a connection-level
    failure, up to `max_retries` times. Returns the last response as-is
    (even a failing one) so the caller's usual _raise_for_response still
    handles the final status code; only raises KotobaApiError itself if
    every attempt failed to connect at all.
    """
    resp = None
    for attempt in range(max_retries + 1):
        try:
            resp = send()
        except requests.RequestException as exc:
            if attempt >= max_retries:
                raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
            time.sleep(_retry_delay(attempt, None))
            continue

        if resp.ok or resp.status_code not in _RETRYABLE_STATUS_CODES or attempt >= max_retries:
            return resp
        time.sleep(_retry_delay(attempt, resp))
    return resp


def _raise_for_response(resp):
    if resp.status_code == 401:
        raise KotobaApiError(
            "Kotoba rejected the session cookie (not logged in / expired). "
            "Copy a fresh Cookie header from DevTools and try again.",
            status_code=401,
        )
    if not resp.ok:
        detail = _extract_error_detail(resp)
        raise KotobaApiError(f"Kotoba API error {resp.status_code}: {detail}", status_code=resp.status_code)


def test_connection(cookie_header: str, max_retries: int = MAX_RETRIES) -> dict:
    """Hits GET /users/me. Returns the user's JSON on success, raises
    KotobaApiError otherwise.
    """
    resp = _send_with_retry(
        lambda: requests.get(f"{BASE_URL}/users/me", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS),
        max_retries=max_retries,
    )
    _raise_for_response(resp)
    return resp.json()


def list_my_decks(cookie_header: str, max_retries: int = MAX_RETRIES) -> list:
    """GET /users/me/decks. Returns the logged-in user's decks as raw dicts
    - fields include _id, name, shortName, hidden, public, lastModified per
    the CustomDeckModel schema, but that schema isn't publicly documented,
    so callers should read fields defensively with .get().
    """
    resp = _send_with_retry(
        lambda: requests.get(
            f"{BASE_URL}/users/me/decks", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        ),
        max_retries=max_retries,
    )
    _raise_for_response(resp)
    return resp.json()


def delete_deck(cookie_header: str, deck_id: str, max_retries: int = MAX_RETRIES) -> None:
    """DELETE /decks/{id}. Requires the logged-in user to own the deck."""
    resp = _send_with_retry(
        lambda: requests.delete(
            f"{BASE_URL}/decks/{deck_id}", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        ),
        max_retries=max_retries,
    )
    _raise_for_response(resp)


def _cards_payload(cards: list) -> list:
    return [
        {
            "question": card.question,
            "answers": card.answers,
            "comment": card.comment,
            "instructions": card.instructions,
            "questionCreationStrategy": card.render_as,
        }
        for card in cards
    ]


def create_deck(
    cookie_header: str,
    name: str,
    short_name: str,
    cards: list,
    description: str = "",
    public: bool = False,
    hidden: bool = True,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """POST /decks. Returns {"id": ..., "readwrite_secret": ...}.

    POST isn't naturally idempotent, so a retry after a connection error
    could in principle create a duplicate if the first attempt actually
    reached the server. In practice this is covered: Kotoba's own
    checkShortNameUnique middleware runs before deck creation, and
    short_name is deterministic from the deck name, so a genuine duplicate
    attempt just gets rejected with a clear "name taken" error (surfaced
    normally through _raise_for_response) instead of silently creating a
    second deck.
    """
    body = {
        "name": name,
        "shortName": short_name,
        "description": description,
        "cards": _cards_payload(cards),
        "public": public,
        "hidden": hidden,
    }
    resp = _send_with_retry(
        lambda: requests.post(
            f"{BASE_URL}/decks", json=body, headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        ),
        max_retries=max_retries,
    )
    _raise_for_response(resp)
    data = resp.json()
    return {
        "id": data.get("_id") or data.get("id"),
        "readwrite_secret": resp.headers.get(RESPONSE_READWRITE_SECRET_HEADER, ""),
    }


def update_deck(
    cookie_header: str,
    deck_id: str,
    readwrite_secret: str,
    name: str,
    short_name: str,
    cards: list,
    description: str = "",
    max_retries: int = MAX_RETRIES,
) -> dict:
    """PATCH /decks/{id}, authenticated with the deck's own readwrite secret
    (not just the login cookie - Kotoba requires both: a logged-in user AND
    either ownership or this secret). Returns {"readwrite_secret": ...}
    (Kotoba re-issues the secret on every authorized response). PATCH is
    naturally idempotent (same body -> same end state), so retrying on a
    connection error carries none of create_deck's duplicate-creation
    concern.
    """
    body = {
        "name": name,
        "shortName": short_name,
        "description": description,
        "cards": _cards_payload(cards),
    }
    resp = _send_with_retry(
        lambda: requests.patch(
            f"{BASE_URL}/decks/{deck_id}",
            json=body,
            headers=_headers(cookie_header, {REQUEST_SECRET_HEADER: readwrite_secret}),
            timeout=TIMEOUT_SECONDS,
        ),
        max_retries=max_retries,
    )
    _raise_for_response(resp)
    return {"readwrite_secret": resp.headers.get(RESPONSE_READWRITE_SECRET_HEADER, readwrite_secret)}
