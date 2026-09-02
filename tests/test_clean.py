from kotoba import clean


def test_strip_furigana_keep_base():
    assert clean.strip_furigana("食べる[たべる]") == "食べる"


def test_strip_furigana_keep_reading():
    assert clean.strip_furigana("食べる[たべる]", keep="reading") == "たべる"


def test_strip_furigana_leaves_plain_text_alone():
    assert clean.strip_furigana("ねこ") == "ねこ"


def test_clean_field_strips_html_sound_and_furigana():
    raw = "<b>猫[ねこ]</b>[sound:neko.mp3]<br>means cat"
    result = clean.clean_field(raw)
    assert "sound" not in result
    assert "<" not in result
    assert "猫" in result
    assert "ねこ" not in result
    assert "means cat" in result


def test_clean_field_can_keep_reading_instead_of_base():
    result = clean.clean_field("猫[ねこ]", furigana_keep="reading")
    assert result == "ねこ"


def test_clean_field_empty_input():
    assert clean.clean_field("") == ""
    assert clean.clean_field(None) == ""


def test_clean_field_resolves_ruby_html_to_base_text():
    raw = "<ruby>私<rt>わたし</rt></ruby>は<ruby>非常<rt>ひじょう</rt></ruby>に不愉快だ。"
    assert clean.clean_field(raw) == "私は非常に不愉快だ。"


def test_clean_field_resolves_ruby_html_to_reading_text():
    raw = "<ruby>私<rt>わたし</rt></ruby>は<ruby>非常<rt>ひじょう</rt></ruby>に"
    assert clean.clean_field(raw, furigana_keep="reading") == "わたしはひじょうに"


def test_clean_field_handles_ruby_fallback_parens():
    raw = "<ruby>私<rp>(</rp><rt>わたし</rt><rp>)</rp></ruby>"
    assert clean.clean_field(raw) == "私"
    assert clean.clean_field(raw, furigana_keep="reading") == "わたし"


def test_clean_field_ruby_resolution_is_not_gated_by_strip_furigana_brackets():
    raw = "<ruby>私<rt>わたし</rt></ruby>"
    result = clean.clean_field(raw, strip_furigana_brackets=False)
    assert result == "私"


def test_clean_field_can_disable_furigana_stripping():
    result = clean.clean_field("猫[ねこ]", strip_furigana_brackets=False)
    assert result == "猫[ねこ]"


def test_truncate_text_leaves_short_text_alone():
    assert clean.truncate_text("short", 100) == "short"


def test_truncate_text_cuts_at_word_boundary_with_ellipsis():
    text = "one two three four five six seven eight nine ten"
    result = clean.truncate_text(text, 20)
    assert len(result) <= 20
    assert result.endswith("…")
    assert text.startswith(result[:-1].rstrip())


def test_truncate_text_hard_cuts_dense_text_with_no_good_space():
    # No spaces at all near the cut point - must still respect max_length.
    text = "猫" * 50
    result = clean.truncate_text(text, 20)
    assert len(result) == 20
    assert result.endswith("…")


def test_truncate_text_noop_for_non_positive_length():
    assert clean.truncate_text("hello", 0) == "hello"
