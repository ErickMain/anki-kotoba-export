import pytest

from kotoba.presets import (
    AUTO_RUN_BOTH,
    AUTO_RUN_OFF,
    AUTO_RUN_SHUTDOWN,
    AUTO_RUN_STARTUP,
    Preset,
    load_presets,
    presets_from_json,
    presets_to_json,
    save_presets,
    upsert_preset,
)


def test_auto_run_defaults_to_off():
    p = Preset.new("A")
    assert p.auto_run == AUTO_RUN_OFF
    assert not p.matches_auto_trigger(AUTO_RUN_STARTUP)
    assert not p.matches_auto_trigger(AUTO_RUN_SHUTDOWN)


def test_matches_auto_trigger_for_a_specific_trigger():
    p = Preset.new("A")
    p.auto_run = AUTO_RUN_STARTUP
    assert p.matches_auto_trigger(AUTO_RUN_STARTUP)
    assert not p.matches_auto_trigger(AUTO_RUN_SHUTDOWN)


def test_matches_auto_trigger_both_matches_either():
    p = Preset.new("A")
    p.auto_run = AUTO_RUN_BOTH
    assert p.matches_auto_trigger(AUTO_RUN_STARTUP)
    assert p.matches_auto_trigger(AUTO_RUN_SHUTDOWN)


def test_deck_link_roundtrip():
    p = Preset.new("Forgotten Today")
    assert p.get_deck_link("Forgotten Today") is None

    p.set_deck_link("Forgotten Today", "deck123", "secret456")
    link = p.get_deck_link("Forgotten Today")
    assert link == {"id": "deck123", "secret": "secret456"}


def test_deck_link_is_keyed_by_exact_name_not_preset():
    p = Preset.new("Forgotten Today")
    p.set_deck_link("Forgotten Today", "deck123", "secret456")
    # A different rendered name (e.g. user typed a custom name to keep a
    # snapshot) has no link yet, even though it's the same preset.
    assert p.get_deck_link("Forgotten Today - keep this one") is None


def test_duplicate_gets_a_fresh_id_and_default_copy_name():
    p = Preset.new("Leeches")
    p.tags = ["N3"]
    clone = p.duplicate()

    assert clone.id != p.id
    assert clone.name == "Leeches (copy)"
    assert clone.tags == ["N3"]


def test_duplicate_accepts_a_custom_name():
    p = Preset.new("Leeches")
    clone = p.duplicate(new_name="Leeches - N4")
    assert clone.name == "Leeches - N4"


def test_duplicate_does_not_carry_over_deck_links():
    p = Preset.new("Forgotten Today")
    p.set_deck_link("Forgotten Today", "deck123", "secret456")
    clone = p.duplicate()

    assert clone.deck_links == {}
    # The original is untouched.
    assert p.get_deck_link("Forgotten Today") == {"id": "deck123", "secret": "secret456"}


def test_duplicate_copies_note_type_mappings_independently():
    p = Preset.new("Vocab")
    p.set_field_mapping("Japanese", "Expression", "Reading", "Meaning")
    clone = p.duplicate()

    clone.set_field_mapping("Mining", "Word", "WordReading", "Glossary")

    assert p.field_mapping_for("Mining") is None  # editing the clone didn't touch the original
    assert clone.field_mapping_for("Japanese")["expression_field"] == "Expression"


def test_preset_survives_config_roundtrip_with_deck_links():
    p = Preset.new("Forgotten Today")
    p.set_deck_link("Forgotten Today", "deck123", "secret456")
    config = save_presets({}, [p])

    loaded = load_presets(config)[0]
    assert loaded.get_deck_link("Forgotten Today") == {"id": "deck123", "secret": "secret456"}


def test_from_dict_ignores_unknown_legacy_fields_and_fills_defaults():
    # Simulates loading a preset saved by an older version of the addon,
    # before deck_links existed (it used to store a single kotoba_deck_id).
    legacy = {
        "id": "abc",
        "name": "Old preset",
        "kotoba_deck_id": "stale-id",
        "kotoba_readwrite_secret": "stale-secret",
    }
    p = Preset.from_dict(legacy)
    assert p.name == "Old preset"
    assert p.deck_links == {}
    assert p.get_deck_link("anything") is None


def test_field_mapping_roundtrip():
    p = Preset.new("Vocab")
    assert p.field_mapping_for("Japanese") is None

    p.set_field_mapping("Japanese", "Expression", "Reading", "Meaning")
    mapping = p.field_mapping_for("Japanese")
    assert mapping == {"expression_field": "Expression", "reading_field": "Reading", "meaning_field": "Meaning"}


def test_field_mapping_supports_multiple_note_types():
    p = Preset.new("Vocab")
    p.set_field_mapping("Japanese", "Expression", "Reading", "Meaning")
    p.set_field_mapping("Mining", "Word", "WordReading", "Glossary")

    assert p.field_mapping_for("Japanese")["expression_field"] == "Expression"
    assert p.field_mapping_for("Mining")["expression_field"] == "Word"
    assert p.field_mapping_for("Basic") is None


def test_from_dict_migrates_legacy_single_note_type_preset():
    # Simulates a preset saved before multi-note-type support (0.2.0 and
    # earlier): a single note_type + 3 top-level field names.
    legacy = {
        "id": "abc",
        "name": "Forgotten Today",
        "note_type": "Japanese",
        "expression_field": "Expression",
        "reading_field": "Reading",
        "meaning_field": "Meaning",
    }
    p = Preset.from_dict(legacy)
    assert p.field_mapping_for("Japanese") == {
        "expression_field": "Expression",
        "reading_field": "Reading",
        "meaning_field": "Meaning",
    }


def test_from_dict_prefers_note_type_mappings_over_legacy_fields_if_both_present():
    # Shouldn't happen in practice, but a dict with both should not let the
    # legacy migration clobber an already-migrated/newer note_type_mappings.
    d = {
        "id": "abc",
        "name": "X",
        "note_type": "Old",
        "expression_field": "OldField",
        "note_type_mappings": {"New": {"expression_field": "NewField", "reading_field": "", "meaning_field": ""}},
    }
    p = Preset.from_dict(d)
    assert p.field_mapping_for("Old") is None
    assert p.field_mapping_for("New")["expression_field"] == "NewField"


def test_upsert_preset_updates_existing_by_id():
    p = Preset.new("A")
    config = save_presets({}, [p])
    p.name = "A renamed"
    config = upsert_preset(config, p)

    presets = load_presets(config)
    assert len(presets) == 1
    assert presets[0].name == "A renamed"


def test_presets_json_roundtrip():
    a = Preset.new("Forgotten Today")
    a.tags = ["N3"]
    a.set_deck_link("Forgotten Today", "deck1", "secret1")
    b = Preset.new("Leeches")

    text = presets_to_json([a, b])
    loaded = presets_from_json(text)

    assert [p.name for p in loaded] == ["Forgotten Today", "Leeches"]
    assert loaded[0].tags == ["N3"]
    assert loaded[0].get_deck_link("Forgotten Today") == {"id": "deck1", "secret": "secret1"}
    assert loaded[0].id == a.id


def test_presets_from_json_rejects_non_array():
    with pytest.raises(ValueError):
        presets_from_json('{"id": "a", "name": "not a list"}')


def test_presets_from_json_rejects_entry_missing_required_fields():
    with pytest.raises(ValueError):
        presets_from_json('[{"name": "missing id"}]')


def test_presets_from_json_rejects_malformed_json():
    with pytest.raises(ValueError):
        presets_from_json("not json at all")


def test_import_upserts_by_id_into_existing_config():
    a = Preset.new("A")
    config = save_presets({}, [a])

    # Simulate re-importing an export that has an updated version of "A"
    # plus a brand new preset "B".
    a_updated = Preset.from_dict(a.to_dict())
    a_updated.name = "A (updated)"
    b = Preset.new("B")

    for preset in (a_updated, b):
        config = upsert_preset(config, preset)

    names = {p.name for p in load_presets(config)}
    assert names == {"A (updated)", "B"}
