from kotoba import format as kf


def test_make_short_name_slugifies():
    assert kf.make_short_name("Forgotten Today") == "forgotten_today"
    assert kf.make_short_name("N3  Vocab!!") == "n3_vocab"


def test_make_short_name_collapses_separator_runs():
    assert kf.make_short_name("a - b") == "a_b"


def test_make_short_name_truncates_and_never_empty():
    assert kf.make_short_name("a" * 40) == "a" * kf.SHORT_NAME_MAX_LENGTH
    assert kf.make_short_name("!!!") == "deck"


def test_build_csv_header_and_row():
    card = kf.KotobaCard(question="猫", answers=["ねこ"], comment="cat", instructions="Type the reading!")
    csv_text = kf.build_csv([card])
    assert csv_text.startswith(kf.BOM + "Question,Answers,Comment,Instructions,Render as")
    assert "猫,ねこ,cat,Type the reading!,TEXT" in csv_text


def test_build_csv_joins_multiple_answers():
    card = kf.KotobaCard(question="行く", answers=["いく", "ゆく"])
    csv_text = kf.build_csv([card])
    assert "いく,ゆく" in csv_text


def test_csv_safe_escapes_formula_trigger_characters():
    for trigger in ("=", "+", "-", "@"):
        assert kf.csv_safe(f"{trigger}cmd|'/bin/sh'!A1").startswith("'" + trigger)


def test_csv_safe_leaves_normal_text_alone():
    assert kf.csv_safe("普通のテキスト") == "普通のテキスト"
    assert kf.csv_safe("") == ""


def test_build_csv_escapes_formula_injection_in_every_free_text_field():
    card = kf.KotobaCard(
        question="=1+1",
        answers=["+CMD"],
        comment="-2+3",
        instructions="@SUM(A1:A2)",
    )
    csv_text = kf.build_csv([card])
    assert "'=1+1" in csv_text  # escaped, not written as a raw leading formula
    assert "'+CMD" in csv_text
    assert "'-2+3" in csv_text
    assert "'@SUM(A1:A2)" in csv_text


def test_validate_cards_flags_empty_question_and_answer():
    empty_question = kf.KotobaCard(question="", answers=["a"])
    empty_answer = kf.KotobaCard(question="q", answers=[])
    warnings = kf.validate_cards([empty_question, empty_answer])
    assert any("empty question" in w for w in warnings)
    assert any("empty answer" in w for w in warnings)


def test_validate_cards_flags_over_length():
    long_question = kf.KotobaCard(question="a" * (kf.TEXT_QUESTION_MAX_LENGTH + 1), answers=["a"])
    warnings = kf.validate_cards([long_question])
    assert any("over Kotoba's" in w for w in warnings)


def test_merge_duplicate_questions_unions_answers_and_comments():
    cards = [
        kf.KotobaCard(question="表", answers=["ひょう"], comment="table, list"),
        kf.KotobaCard(question="表", answers=["おもて"], comment="front, surface"),
    ]
    merged = kf.merge_duplicate_questions(cards)
    assert len(merged) == 1
    assert merged[0].answers == ["ひょう", "おもて"]
    assert merged[0].comment == "table, list / front, surface"


def test_merge_duplicate_questions_dedupes_repeated_answer():
    cards = [
        kf.KotobaCard(question="行く", answers=["いく"]),
        kf.KotobaCard(question="行く", answers=["いく", "ゆく"]),
    ]
    merged = kf.merge_duplicate_questions(cards)
    assert merged[0].answers == ["いく", "ゆく"]


def test_merge_duplicate_questions_leaves_unique_questions_alone():
    cards = [kf.KotobaCard(question="猫", answers=["ねこ"]), kf.KotobaCard(question="犬", answers=["いぬ"])]
    merged = kf.merge_duplicate_questions(cards)
    assert len(merged) == 2


def test_merge_duplicate_questions_does_not_merge_blank_questions_together():
    cards = [kf.KotobaCard(question="", answers=["a"]), kf.KotobaCard(question="", answers=["b"])]
    merged = kf.merge_duplicate_questions(cards)
    assert len(merged) == 2


def test_merge_duplicate_questions_unions_source_note_ids():
    cards = [
        kf.KotobaCard(question="表", answers=["ひょう"], source_note_ids=[1]),
        kf.KotobaCard(question="表", answers=["おもて"], source_note_ids=[2]),
    ]
    merged = kf.merge_duplicate_questions(cards)
    assert merged[0].source_note_ids == [1, 2]


def test_merge_duplicate_questions_keeps_source_note_ids_for_unique_questions():
    cards = [kf.KotobaCard(question="猫", answers=["ねこ"], source_note_ids=[1])]
    merged = kf.merge_duplicate_questions(cards)
    assert merged[0].source_note_ids == [1]


def test_validate_cards_flags_duplicate_questions():
    a = kf.KotobaCard(question="猫", answers=["ねこ"])
    b = kf.KotobaCard(question="猫", answers=["みょう"])
    warnings = kf.validate_cards([a, b])
    assert any("duplicate" in w.lower() for w in warnings)


def test_looks_like_citation_flags_dictionary_source_stamps():
    assert kf.looks_like_citation("Jitendex.org [2026-01-04]")
    assert kf.looks_like_citation("see https://example.com")
    assert kf.looks_like_citation("weblio.co.jp entry")


def test_looks_like_citation_leaves_real_readings_alone():
    assert not kf.looks_like_citation("はんげき")
    assert not kf.looks_like_citation("かえりうち")
    assert not kf.looks_like_citation("")


def test_validate_cards_flags_citation_like_answer():
    card = kf.KotobaCard(question="反撃", answers=["Jitendex.org [2026-01-04]"])
    warnings = kf.validate_cards([card])
    assert any("citation" in w for w in warnings)


def test_validate_cards_flags_citation_like_question():
    card = kf.KotobaCard(question="Jitendex.org [2026-01-04]", answers=["はんげき"])
    warnings = kf.validate_cards([card])
    assert any("citation" in w for w in warnings)


def test_validate_cards_clean_deck_has_no_warnings():
    card = kf.KotobaCard(question="猫", answers=["ねこ"], comment="cat", instructions="Type the reading!")
    assert kf.validate_cards([card]) == []


def test_summarize_warnings_empty_list_is_blank():
    assert kf.summarize_warnings([]) == ""


def test_summarize_warnings_shows_all_when_within_max():
    assert kf.summarize_warnings(["a", "b"]) == "2 warning(s): a; b"


def test_summarize_warnings_truncates_and_counts_remainder():
    warnings = [f"w{i}" for i in range(5)]
    result = kf.summarize_warnings(warnings, max_shown=3)
    assert result == "5 warning(s): w0; w1; w2 (+2 more)"


def test_summarize_warnings_exactly_at_max_shown_has_no_remainder_note():
    warnings = ["a", "b", "c"]
    result = kf.summarize_warnings(warnings, max_shown=3)
    assert result == "3 warning(s): a; b; c"
    assert "more" not in result


def test_validate_cards_uses_shorter_limit_for_image_questions():
    # Fits under TEXT's 400-char cap but not IMAGE's 20-char cap.
    question = "a" * 30
    text_card = kf.KotobaCard(question=question, answers=["a"], render_as=kf.RENDER_AS_TEXT)
    image_card = kf.KotobaCard(question=question, answers=["a"], render_as=kf.RENDER_AS_IMAGE)

    assert kf.validate_cards([text_card]) == []
    warnings = kf.validate_cards([image_card])
    assert any("IMAGE" in w for w in warnings)
