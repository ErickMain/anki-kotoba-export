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


def test_clean_field_joins_glossary_list_items_with_commas():
    # Yomitan/Jitendex mining templates wrap each gloss word in its own
    # <li> inside <ul data-sc-content="glossary"> - generic tag-stripping
    # (both Anki's own strip_html and this module's fallback) deletes <li>
    # boundaries with nothing in their place, jamming the words together.
    raw = '<ul data-sc-content="glossary"><li>willpower</li><li>guts</li><li>spirit</li></ul>'
    assert clean.clean_field(raw) == "willpower, guts, spirit"


def test_clean_field_does_not_join_an_unrelated_list():
    # A <ul> with no data-sc-content="glossary" attribute is left to the
    # generic block-separator handling below (one item per line), not the
    # comma-join specific to that one marked structure.
    raw = "<ul><li>根性骨</li><li>根性焼き</li></ul>"
    result = clean.clean_field(raw)
    assert result == "根性骨\n根性焼き"


def test_clean_field_separates_adjacent_tag_spans_with_a_space():
    # Yomitan/Jitendex wraps each short label (conjugation class,
    # transitivity, "usually kana", etc.) in its own
    # <span data-sc-class="tag">, relying on a CSS margin for the visible
    # gap - lost once tags are stripped, e.g. "5-dantransitivekana".
    raw = (
        '<span data-sc-class="tag">5-dan</span>'
        '<span data-sc-class="tag">transitive</span>'
        '<span data-sc-class="tag">kana</span>'
    )
    assert clean.clean_field(raw) == "5-dan transitive kana"


def test_clean_field_does_not_insert_a_space_for_a_plain_span():
    # Only spans specifically marked data-sc-class="tag" are targeted -
    # a generic <span> (e.g. wrapping one word inside an example sentence)
    # must not get an inserted space, or real running text would be
    # wrongly broken apart.
    raw = '後はまーくんが<span data-sc-content="example-keyword">根性</span>見せなきゃ'
    assert clean.clean_field(raw) == "後はまーくんが根性見せなきゃ"


def test_clean_field_inserts_newline_for_div_and_li_and_p():
    # Confirmed against Anki's actual strip_html source (rslib/src/text.rs)
    # that it is a blind tag-stripper with no special handling for any of
    # these - checked here through the fallback path (no anki module in
    # this test environment) but the separator-insertion this exercises
    # runs identically before either implementation is called.
    assert clean.clean_field("<div>a</div><div>b</div>") == "a\nb"
    assert clean.clean_field("<p>a</p><p>b</p>") == "a\nb"
    assert clean.clean_field("<ul><li>a</li><li>b</li></ul>") == "a\nb"
    assert clean.clean_field("a<br>b<br/>c<br />d") == "a\nb\nc\nd"


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


# Within-entry separation - real excerpts from a live mined export where a
# single Jitendex entry's own gloss list, example sentence, translation,
# and second-sense glosses ran together with no separator at all.


def test_format_comment_sections_separates_gloss_list_from_japanese_example():
    # From 突きつける.
    text = "to thrust (at someone)to stickto point (a gun)その泥棒は少年にナイフを突きつけようとした。"
    result = clean.format_comment_sections(text)
    assert "\n" in result
    assert result.split("\n")[-1].startswith("その泥棒")
    assert result.replace("\n", "") == text


def test_format_comment_sections_separates_japanese_example_from_translation():
    text = "その泥棒は少年にナイフを突きつけようとした。The robber tried to plunge the knife into the boy."
    result = clean.format_comment_sections(text)
    assert result == (
        "その泥棒は少年にナイフを突きつけようとした。\n"
        "The robber tried to plunge the knife into the boy."
    )


def test_format_comment_sections_separates_translation_from_trailing_second_sense():
    # From 根性 - the translation runs directly into a second sense's gloss
    # list with no separator.
    text = "I've set the stage so now you just have to show some guts, OK?characternaturedispositionpersonality"
    result = clean.format_comment_sections(text)
    assert result == (
        "I've set the stage so now you just have to show some guts, OK?\n"
        "characternaturedispositionpersonality"
    )


def test_format_comment_sections_separates_forms_tag_with_no_preceding_punctuation():
    # From 絶つ - "forms" (Jitendex's alternate-spellings tag) glued
    # directly onto the last gloss, itself glued onto the first alternate
    # spelling.
    text = "to abstain (from)to give upforms断つ絶つ"
    result = clean.format_comment_sections(text)
    assert result == "to abstain (from)to give up\nforms\n断つ絶つ"


def test_format_comment_sections_does_not_split_a_digit_directly_before_kanji():
    # "第5版" (5th edition) is normal Japanese typography with an embedded
    # Arabic numeral - must not be mistaken for an English-to-Japanese
    # boundary the way a Latin letter directly before kanji would be.
    text = "(新和英大辞典 第5版) にゅうもん【入門】1 〔弟子入り〕"
    result = clean.format_comment_sections(text)
    assert "第5版" in result


def test_format_comment_sections_leaves_citation_domain_intact():
    # Jitendex.org's own citation must not be split by the same rule that
    # separates a translation from a following gloss run.
    text = "(★, Jitendex.org [2026-04-04]) noun willpower"
    result = clean.format_comment_sections(text)
    assert "Jitendex.org" in result
    assert "Jitendex.\norg" not in result


def test_format_comment_sections_real_kokoro_excerpt_end_to_end():
    # The full real 根性 comment field, exactly as mined - verifies the
    # whole pipeline together rather than one boundary at a time.
    text = (
        "(★, Jitendex.org [2026-04-04]) nounwillpowergutsdeterminationgritspirit"
        "セッティングは整えておいたから、後はまーくんが根性見せなきゃダメだからね？"
        "I've set the stage so now you just have to show some guts, OK?"
        "characternaturedispositionpersonality"
    )
    result = clean.format_comment_sections(text)
    lines = result.split("\n")
    assert lines[0] == "(★, Jitendex.org [2026-04-04]) nounwillpowergutsdeterminationgritspirit"
    assert lines[1].startswith("セッティングは")
    assert lines[1].endswith("？")
    assert lines[2] == "I've set the stage so now you just have to show some guts, OK?"
    assert lines[3] == "characternaturedispositionpersonality"
    # Nothing dropped - still just whitespace insertion.
    assert result.replace("\n", "") == text


# Real raw field HTML, exactly as exported from a live 根性 note (Yomitan/
# Jitendex-style mining template) - the ground-truth case that surfaced
# both the missing glossary-list-comma-join and the missing block-tag
# separator handling, verified end to end through clean_field ->
# format_comment_sections together, not just one boundary at a time.
_KONJOU_RAW_HTML = (
    '<div style="text-align: left;" class="yomitan-glossary"><ol>'
    '<li data-dictionary="Jitendex.org [2026-04-04]"><i>(★, Jitendex.org [2026-04-04])</i> '
    '<span><ul data-sc-content="sense-groups" lang="ja"><li data-sc-content="sense-group">'
    '<span data-sc-class="tag" data-sc-code="n" data-sc-content="part-of-speech-info" '
    'title="noun (common) (futsuumeishi)">noun</span><ol>'
    '<li data-sc-content="sense" style="list-style-type: &quot;①&quot;;">'
    '<ul data-sc-content="glossary"><li>willpower</li><li>guts</li><li>determination</li>'
    '<li>grit</li><li>spirit</li></ul>'
    '<div data-sc-content="extra-info"><div><div data-sc-class="extra-box" '
    'data-sc-content="example-sentence" data-sc-source="75553">'
    '<div data-sc-content="example-sentence-a"><span lang="ja">'
    "セッティングは整えておいたから、後はまーくんが"
    '<span data-sc-content="example-keyword">根性</span>見せなきゃダメだからね？</span></div>'
    '<div data-sc-content="example-sentence-b"><span lang="en">'
    "I've set the stage so now you just have to show some guts, OK?"
    "</span></div></div></div></div></li>"
    '<li data-sc-content="sense" style="list-style-type: &quot;②&quot;;">'
    '<ul data-sc-content="glossary"><li>character</li><li>nature</li>'
    "<li>disposition</li><li>personality</li></ul></li></ol></li></ul>"
    '<div data-sc-content="attribution">'
    '<a href="https://www.edrdg.org/jmwsgi/entr.py?svc=jmdict&amp;q=1290210">'
    "<span>JMdict</span><span style=\"display:none;\"></span></a> | "
    '<a href="https://tatoeba.org/en/sentences/show/75553">'
    '<span>Tatoeba</span><span style="display:none;"></span></a></div></span></li>'
    '<li data-dictionary="大辞林　第四版">'
    "<i>(大辞林　第四版)</i> <span>"
    '<span data-sc-name="見出部"><span data-sc-name="見出仮名" lang="ja" '
    'style="font-weight: bold;">'
    'こん<span data-sc-name="語構成" style="margin-right: 0.5em;"></span>じょう</span>'
    '<span data-sc-name="歴史仮名" lang="ja" style="font-size: 0.6em;">(—じやう)</span>'
    '<span data-sc-name="表記G" lang="ja">【<span data-sc-name="標準表記" lang="ja">根性</span>】</span>'
    "</span>"
    '<div data-sc-name="解説部"><div data-sc-name="大語義"><div data-sc-name="準大語義">'
    '<div data-sc-name="中語義"><div data-sc-name="語義G">'
    '<span data-sc-name="語義Gnum">①</span>'
    '<span data-sc-name="語釈" lang="ja">生まれつきの性質。根本的な考え方。</span>'
    "</div></div></div></div></div></span></li>"
    '<li data-dictionary="JMdict"><i>(JMdict)</i> <span lang="ja">'
    "こんじょう【根性】<br>〔n〕<br>"
    "1 willpower | guts | determination | grit | spirit<br>"
    "2 character | nature | disposition | personality</span></li>"
    "</ol></div>"
)


def test_real_konjou_glossary_end_to_end():
    cleaned = clean.clean_field(_KONJOU_RAW_HTML)
    result = clean.format_comment_sections(cleaned)
    lines = result.split("\n")

    assert lines[0] == "(★, Jitendex.org [2026-04-04])"
    assert lines[1] == "noun"
    assert lines[2] == "willpower, guts, determination, grit, spirit"
    assert lines[3].startswith("セッティングは")
    assert lines[4] == "I've set the stage so now you just have to show some guts, OK?"
    assert lines[5] == "character, nature, disposition, personality"
    assert "JMdict | Tatoeba" in lines
    assert any(line.startswith("(大辞林") and "第四版" in line for line in lines)
    assert any(line.startswith("(JMdict)") for line in lines)
    # No tags, no HTML entities, and no blank lines anywhere in the result.
    assert "<" not in result
    assert "&quot;" not in result
    assert "\n\n" not in result
