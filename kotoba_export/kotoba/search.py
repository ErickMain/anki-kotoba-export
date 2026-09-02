"""Builds Anki search strings for the quick-filter chips (forgotten today,
leech, suspended, due) plus tags and a raw search box, and runs them against
an Anki collection.
"""
from dataclasses import dataclass, field

# Anki search fragments for each quick-filter. `rated:1:1` means "answered
# in the last day with ease 1 (the Again button)" - the closest match Anki's
# search language has to "cards I forgot today".
FORGOTTEN_TODAY = "rated:1:1"
LEECH = "tag:leech"
SUSPENDED = "is:suspended"
DUE = "is:due"


@dataclass
class QueryFilters:
    forgotten_today: bool = False
    leech: bool = False
    suspended: bool = False
    due: bool = False
    tags: list = field(default_factory=list)
    deck: str = ""
    raw_query: str = ""

    def is_empty(self) -> bool:
        return not (
            self.forgotten_today
            or self.leech
            or self.suspended
            or self.due
            or self.tags
            or self.deck.strip()
            or self.raw_query.strip()
        )


def _quote_tag(tag: str) -> str:
    # Anki tags can contain spaces/special chars; quote defensively.
    escaped = tag.replace('"', '\\"')
    return f'tag:"{escaped}"'


def _quote_deck(deck: str) -> str:
    # deck:X also matches X's subdecks, which is what "pick a deck" should mean.
    escaped = deck.replace('"', '\\"')
    return f'deck:"{escaped}"'


def build_query(filters: QueryFilters) -> str:
    """Combine all active filters into one Anki search string, AND-ed together."""
    parts = []
    if filters.forgotten_today:
        parts.append(FORGOTTEN_TODAY)
    if filters.leech:
        parts.append(LEECH)
    if filters.suspended:
        parts.append(SUSPENDED)
    if filters.due:
        parts.append(DUE)
    for tag in filters.tags:
        parts.append(_quote_tag(tag))
    if filters.deck.strip():
        parts.append(_quote_deck(filters.deck.strip()))
    if filters.raw_query.strip():
        parts.append(f"({filters.raw_query.strip()})")
    return " ".join(parts)


def find_matching_note_ids(col, query: str) -> list:
    """Run `query` as a card search and return unique note ids, in the order
    their first matching card was found. Card-level filters (leech,
    suspended, forgotten today...) can only be searched at the card level in
    Anki, but Kotoba decks are built per-note, so we dedupe here.
    """
    card_ids = col.find_cards(query)
    seen = set()
    note_ids = []
    for cid in card_ids:
        nid = col.get_card(cid).nid
        if nid not in seen:
            seen.add(nid)
            note_ids.append(nid)
    return note_ids
