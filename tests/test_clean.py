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


def test_truncate_text_prefers_a_newline_break_over_a_hard_cut():
    text = "first section" + "\n" + ("x" * 30)
    result = clean.truncate_text(text, 20)
    assert result == "first section…"


# format_comment_sections - real excerpts from mined (Yomitan/Jitendex-style)
# notes, where several dictionaries end up concatenated into one field with
# no separator at all.


def test_format_comment_sections_splits_jitendex_and_kokugo_dictionaries():
    # Shortened version of the actual 入門 comment field.
    text = (
        "(★, Jitendex.org [2026-04-04]) noun entering through a gateJMdict"
        "(大辞林 第四版) にゅうもん(にふ—)【入門】（名）スル"
        "(新和英大辞典 第5版) にゅうもん【入門】1 〔弟子入り〕"
        "(JMdict) にゅうもん【入門】〔n・vi・vs〕1 becoming a pupil (of)"
    )
    result = clean.format_comment_sections(text)
    sections = result.split("\n")
    assert sections[0] == "(★, Jitendex.org [2026-04-04]) noun entering through a gate"
    assert sections[1] == "JMdict"
    assert sections[2].startswith("(大辞林 第四版)")
    assert sections[3].startswith("(新和英大辞典 第5版)")
    assert sections[4].startswith("(JMdict)")
    # Nothing was dropped - only whitespace inserted.
    assert result.replace("\n", "") == text


def test_format_comment_sections_splits_trailing_jmdict_tatoeba_footer():
    text = "The spider responds with a swift attack.JMdict | Tatoeba"
    result = clean.format_comment_sections(text)
    assert result == "The spider responds with a swift attack.\nJMdict | Tatoeba"


def test_format_comment_sections_does_not_split_incidental_parens():
    # Real JMdict gloss text (とうてい) - "(cannot)"/"(not)" are legitimate
    # parenthetical gloss content, not dictionary-name markers, and must be
    # left alone: this is exactly the "full parsing is too fragile" case
    # that ruled out trying to pick a single dictionary.
    text = "(cannot) possibly | (not) by any means | (not) at all | utterly | absolutely"
    assert clean.format_comment_sections(text) == text


def test_format_comment_sections_no_marker_at_all_is_unchanged():
    text = "just a plain comment with no dictionary markers"
    assert clean.format_comment_sections(text) == text


def test_format_comment_sections_marker_at_the_very_start_gets_no_leading_break():
    text = "(JMdict) some gloss"
    result = clean.format_comment_sections(text)
    assert not result.startswith("\n")
    assert result == text


def test_format_comment_sections_empty_input():
    assert clean.format_comment_sections("") == ""
