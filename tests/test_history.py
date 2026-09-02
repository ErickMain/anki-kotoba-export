from datetime import datetime

from kotoba import history


def test_new_entry_uses_iso_timestamp():
    entry = history.new_entry(
        "Forgotten Today", "Anki Forgotten Today", 12, history.OUTCOME_UPLOADED, now=datetime(2026, 9, 2, 14, 23, 1)
    )
    assert entry.timestamp == "2026-09-02T14:23:01"
    assert entry.triggered_by == history.TRIGGER_MANUAL
    assert entry.detail == ""


def test_append_and_load_roundtrip():
    config = {}
    entry = history.new_entry("A", "Deck A", 5, history.OUTCOME_COPIED)
    config = history.append_entry(config, entry)

    loaded = history.load_history(config)
    assert len(loaded) == 1
    assert loaded[0].preset_name == "A"
    assert loaded[0].card_count == 5
    assert loaded[0].outcome == history.OUTCOME_COPIED


def test_append_entry_preserves_order():
    config = {}
    config = history.append_entry(config, history.new_entry("A", "Deck A", 1, history.OUTCOME_COPIED))
    config = history.append_entry(config, history.new_entry("B", "Deck B", 2, history.OUTCOME_UPLOADED))

    loaded = history.load_history(config)
    assert [e.preset_name for e in loaded] == ["A", "B"]


def test_append_entry_caps_at_max_entries():
    config = {}
    for i in range(history.MAX_ENTRIES + 10):
        config = history.append_entry(config, history.new_entry(f"preset-{i}", "Deck", 1, history.OUTCOME_COPIED))

    loaded = history.load_history(config)
    assert len(loaded) == history.MAX_ENTRIES
    # Oldest entries were dropped, newest kept.
    assert loaded[0].preset_name == "preset-10"
    assert loaded[-1].preset_name == f"preset-{history.MAX_ENTRIES + 9}"


def test_clear_history():
    config = {}
    config = history.append_entry(config, history.new_entry("A", "Deck A", 1, history.OUTCOME_COPIED))
    config = history.clear_history(config)
    assert history.load_history(config) == []


def test_from_dict_ignores_unknown_fields():
    entry = history.HistoryEntry.from_dict(
        {
            "timestamp": "2026-09-02T14:23:01",
            "preset_name": "A",
            "deck_name": "Deck A",
            "card_count": 3,
            "outcome": "uploaded",
            "some_future_field": "ignored",
        }
    )
    assert entry.preset_name == "A"
    assert entry.detail == ""  # default, since it was missing
