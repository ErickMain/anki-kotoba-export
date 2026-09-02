from kotoba import search
from fakes import FakeCollection, FakeNote


def test_build_query_combines_all_filters():
    filters = search.QueryFilters(
        forgotten_today=True,
        leech=True,
        suspended=True,
        due=True,
        tags=["N3", "vocab"],
        raw_query="deck:Japanese",
    )
    query = search.build_query(filters)
    assert query == (
        'rated:1:1 tag:leech is:suspended is:due tag:"N3" tag:"vocab" (deck:Japanese)'
    )


def test_build_query_empty_when_nothing_set():
    assert search.build_query(search.QueryFilters()) == ""


def test_build_query_quotes_tags_with_special_chars():
    filters = search.QueryFilters(tags=['weird tag "with" quotes'])
    query = search.build_query(filters)
    assert query == 'tag:"weird tag \\"with\\" quotes"'


def test_build_query_includes_deck_filter():
    filters = search.QueryFilters(deck="2 Mining", forgotten_today=True)
    query = search.build_query(filters)
    assert query == 'rated:1:1 deck:"2 Mining"'


def test_build_query_ignores_blank_deck():
    assert search.build_query(search.QueryFilters(deck="  ")) == ""


def test_find_matching_note_ids_dedupes_across_cards():
    notes = {
        1: FakeNote("Basic", {"Front": "a"}, nid=1),
        2: FakeNote("Basic", {"Front": "b"}, nid=2),
    }
    col = FakeCollection(notes)
    col.cards = [
        col.cards[0],
        col.cards[1],
        type(col.cards[0])(cid=99, nid=1),  # a second card on note 1
    ]
    note_ids = search.find_matching_note_ids(col, "")
    assert note_ids == [1, 2]
