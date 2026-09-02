from datetime import date

from fakes import FakeCollection, FakeNote

from kotoba import export
from kotoba.presets import Preset


def _make_preset(**overrides):
    p = Preset.new("Test preset")
    p.set_field_mapping("Japanese", "Expression", "Reading", "Meaning")
    for key, value in overrides.items():
        setattr(p, key, value)
    return p


def test_build_cards_maps_fields_and_defaults_to_type_the_reading():
    notes = {
        1: FakeNote(
            "Japanese",
            {"Expression": "猫[ねこ]", "Reading": "ねこ", "Meaning": "cat"},
            nid=1,
        )
    }
    col = FakeCollection(notes)
    preset = _make_preset()

    result = export.build_cards_for_preset(col, preset)

    assert result.total_matched_notes == 1
    assert result.skipped_wrong_note_type == 0
    card = result.cards[0]
    assert card.question == "猫"  # furigana bracket stripped from the expression
    assert card.answers == ["ねこ"]
    assert card.comment == "cat"
    assert card.instructions == "Type the reading!"
    assert card.render_as == "IMAGE"  # default: hide the answer from copy/paste


def test_build_cards_skips_notes_of_a_different_note_type():
    notes = {
        1: FakeNote("Japanese", {"Expression": "猫", "Reading": "ねこ", "Meaning": "cat"}, nid=1),
        2: FakeNote("Basic", {"Front": "hello", "Back": "world"}, nid=2),
    }
    col = FakeCollection(notes)
    preset = _make_preset()

    result = export.build_cards_for_preset(col, preset)

    assert len(result.cards) == 1
    assert result.skipped_wrong_note_type == 1


def test_build_cards_pulls_from_multiple_note_types_with_their_own_field_names():
    notes = {
        1: FakeNote("Japanese", {"Expression": "猫", "Reading": "ねこ", "Meaning": "cat"}, nid=1),
        2: FakeNote("Mining", {"Word": "犬", "WordReading": "いぬ", "Glossary": "dog"}, nid=2),
        3: FakeNote("Basic", {"Front": "hello", "Back": "world"}, nid=3),
    }
    col = FakeCollection(notes)
    preset = _make_preset()  # already maps "Japanese"
    preset.set_field_mapping("Mining", "Word", "WordReading", "Glossary")

    result = export.build_cards_for_preset(col, preset)

    assert result.skipped_wrong_note_type == 1  # only the "Basic" note
    questions = {c.question: c for c in result.cards}
    assert questions["猫"].answers == ["ねこ"]
    assert questions["犬"].answers == ["いぬ"]
    assert questions["犬"].comment == "dog"


def test_build_cards_splits_multiple_answers():
    notes = {1: FakeNote("Japanese", {"Expression": "行く", "Reading": "いく、ゆく", "Meaning": "go"}, nid=1)}
    col = FakeCollection(notes)
    preset = _make_preset()

    result = export.build_cards_for_preset(col, preset)

    assert result.cards[0].answers == ["いく", "ゆく"]


def test_build_cards_comment_none_leaves_it_blank():
    notes = {1: FakeNote("Japanese", {"Expression": "猫", "Reading": "ねこ", "Meaning": "cat"}, nid=1)}
    col = FakeCollection(notes)
    preset = _make_preset(comment_source="none")

    result = export.build_cards_for_preset(col, preset)

    assert result.cards[0].comment == ""


def test_build_cards_merges_notes_that_share_a_question():
    notes = {
        1: FakeNote("Japanese", {"Expression": "表", "Reading": "ひょう", "Meaning": "table, list"}, nid=1),
        2: FakeNote("Japanese", {"Expression": "表", "Reading": "おもて", "Meaning": "front, surface"}, nid=2),
    }
    col = FakeCollection(notes)
    preset = _make_preset()

    result = export.build_cards_for_preset(col, preset)

    assert len(result.cards) == 1
    assert result.merged_duplicate_count == 1
    assert result.cards[0].answers == ["ひょう", "おもて"]


def test_build_cards_caps_huge_mined_comment():
    huge_meaning = "definition " * 200  # a JMdict/Jitendex-style wall of text, way over 300 chars
    notes = {1: FakeNote("Japanese", {"Expression": "猫", "Reading": "ねこ", "Meaning": huge_meaning}, nid=1)}
    col = FakeCollection(notes)
    preset = _make_preset()  # comment_max_length defaults to 300

    result = export.build_cards_for_preset(col, preset)

    assert len(result.cards[0].comment) <= 300
    assert result.cards[0].comment.endswith("…")


def test_build_cards_respects_custom_comment_max_length():
    notes = {1: FakeNote("Japanese", {"Expression": "猫", "Reading": "ねこ", "Meaning": "a" * 100}, nid=1)}
    col = FakeCollection(notes)
    preset = _make_preset(comment_max_length=50)

    result = export.build_cards_for_preset(col, preset)

    assert len(result.cards[0].comment) <= 50


def test_render_deck_name_uses_template():
    preset = _make_preset(name="Leeches", deck_name_template="{preset_name} :: {date}")
    name = export.render_deck_name(preset, today=date(2026, 9, 1))
    assert name == "Leeches :: 2026-09-01"
