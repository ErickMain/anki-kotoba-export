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
import requests

BASE_URL = "https://kotobaweb.com/api"
REQUEST_SECRET_HEADER = "Deck-Permissions-Secret"
RESPONSE_READWRITE_SECRET_HEADER = "Deck-Read-Write-Secret"
RESPONSE_PERMISSIONS_HEADER = "Deck-Permissions"

TIMEOUT_SECONDS = 15


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
    """
    raw = raw.strip()
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


def test_connection(cookie_header: str) -> dict:
    """Hits GET /users/me. Returns the user's JSON on success, raises
    KotobaApiError otherwise.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/users/me", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
    _raise_for_response(resp)
    return resp.json()


def list_my_decks(cookie_header: str) -> list:
    """GET /users/me/decks. Returns the logged-in user's decks as raw dicts
    - fields include _id, name, shortName, hidden, public, lastModified per
    the CustomDeckModel schema, but that schema isn't publicly documented,
    so callers should read fields defensively with .get().
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/users/me/decks", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
    _raise_for_response(resp)
    return resp.json()


def delete_deck(cookie_header: str, deck_id: str) -> None:
    """DELETE /decks/{id}. Requires the logged-in user to own the deck."""
    try:
        resp = requests.delete(
            f"{BASE_URL}/decks/{deck_id}", headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
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
) -> dict:
    """POST /decks. Returns {"id": ..., "readwrite_secret": ...}."""
    body = {
        "name": name,
        "shortName": short_name,
        "description": description,
        "cards": _cards_payload(cards),
        "public": public,
        "hidden": hidden,
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/decks", json=body, headers=_headers(cookie_header), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
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
) -> dict:
    """PATCH /decks/{id}, authenticated with the deck's own readwrite secret
    (not just the login cookie - Kotoba requires both: a logged-in user AND
    either ownership or this secret). Returns {"readwrite_secret": ...}
    (Kotoba re-issues the secret on every authorized response).
    """
    body = {
        "name": name,
        "shortName": short_name,
        "description": description,
        "cards": _cards_payload(cards),
    }
    try:
        resp = requests.patch(
            f"{BASE_URL}/decks/{deck_id}",
            json=body,
            headers=_headers(cookie_header, {REQUEST_SECRET_HEADER: readwrite_secret}),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise KotobaApiError(f"Could not reach kotobaweb.com: {exc}") from exc
    _raise_for_response(resp)
    return {"readwrite_secret": resp.headers.get(RESPONSE_READWRITE_SECRET_HEADER, readwrite_secret)}
