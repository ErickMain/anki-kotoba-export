"""Turns raw Anki field HTML into plain text suitable for a Kotoba CSV cell."""
import html
import re

try:
    # Prefer Anki's own implementation when running inside Anki - it handles
    # more edge cases (MathJax, LaTeX, etc.) than we'd want to reimplement.
    from anki.utils import strip_html as _anki_strip_html
except ImportError:  # pytest / any environment without Anki installed
    _anki_strip_html = None

_SOUND_RE = re.compile(r"\[sound:[^\]]*\]")
_TAG_RE = re.compile(r"<[^>]+>")
_FURIGANA_RE = re.compile(r"([^\s\[\]]+)\[([^\[\]]*)\]")
_WHITESPACE_RE = re.compile(r"[ \t　]+")

# Yomitan/mining templates commonly write furigana as literal <ruby> HTML
# rather than Anki's base[reading] bracket syntax - e.g.
# "<ruby>私<rt>わたし</rt></ruby>" for 私 read わたし. Generic tag-stripping
# just deletes the tags and leaves the base and reading text jammed
# together with nothing between them ("私わたし"), so this has to be
# resolved before any generic HTML stripping runs.
_RUBY_RP_RE = re.compile(r"<rp[^>]*>.*?</rp>", re.IGNORECASE | re.DOTALL)
_RUBY_RT_RE = re.compile(r"<rt[^>]*>(.*?)</rt>", re.IGNORECASE | re.DOTALL)
_RUBY_BLOCK_RE = re.compile(r"<ruby[^>]*>.*?</ruby>", re.IGNORECASE | re.DOTALL)
_RUBY_INNER_TAGS_RE = re.compile(r"</?(?:ruby|rb)[^>]*>", re.IGNORECASE)


def _resolve_ruby_html(text: str, keep: str = "base") -> str:
    """Turn <ruby>base<rt>reading</rt></ruby> into plain "base" or "reading"."""
    if "<ruby" not in text.lower():
        return text

    text = _RUBY_RP_RE.sub("", text)
    if keep == "reading":
        def _reading_only(match):
            rt_match = _RUBY_RT_RE.search(match.group(0))
            return rt_match.group(1) if rt_match else ""

        return _RUBY_BLOCK_RE.sub(_reading_only, text)

    text = _RUBY_RT_RE.sub("", text)
    return _RUBY_INNER_TAGS_RE.sub("", text)


_GLOSSARY_LIST_RE = re.compile(
    r'<ul[^>]*data-sc-content="glossary"[^>]*>(.*?)</ul>', re.IGNORECASE | re.DOTALL
)
_LI_OPEN_RE = re.compile(r"<li[^>]*>", re.IGNORECASE)
_LI_CLOSE_RE = re.compile(r"</li\s*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_DIV_OPEN_RE = re.compile(r"<div[^>]*>", re.IGNORECASE)
_P_OPEN_RE = re.compile(r"<p[^>]*>", re.IGNORECASE)
# Yomitan/Jitendex wraps each short label (conjugation class, transitivity,
# "usually kana", etc.) in its own <span data-sc-class="tag">, relying on a
# CSS margin for the visible gap between adjacent ones (e.g.
# "5-dan"/"transitive"/"kana") - lost the same way as everything else here
# once tags are stripped, producing "5-dantransitivekana". Only the
# specific data-sc-class="tag" spans are targeted, not <span> in general -
# <span> is also used for plain inline text (e.g. wrapping a whole example
# sentence, or one word inside it), where inserting a space would wrongly
# break up otherwise-unbroken text.
_TAG_SPAN_OPEN_RE = re.compile(r'<span[^>]*data-sc-class="tag"[^>]*>', re.IGNORECASE)


def _join_glossary_list_items(text: str) -> str:
    """Yomitan/Jitendex mining templates wrap each individual gloss word in
    its own <li> inside a <ul data-sc-content="glossary"> - e.g.
    <ul data-sc-content="glossary"><li>willpower</li><li>guts</li>...</ul>.
    Generic tag-stripping deletes the <li> boundaries with nothing in their
    place, jamming the words together ("willpowerguts..."), so this has to
    be resolved before any generic HTML stripping runs - the same reason
    <ruby> is resolved early, above. Unlike other structural boundaries
    (separated with a newline - see _insert_block_separators below), a
    short list of near-synonyms reads better joined inline than stacked one
    per line, so this specific, narrowly-identified list gets a comma join
    instead.
    """
    if 'data-sc-content="glossary"' not in text:
        return text

    def _join_one_list(match):
        items = _LI_OPEN_RE.split(match.group(1))[1:]  # [0] is text before the first <li>, always empty here
        words = [_LI_CLOSE_RE.sub("", item).strip() for item in items]
        return ", ".join(w for w in words if w)

    return _GLOSSARY_LIST_RE.sub(_join_one_list, text)


def _insert_block_separators(text: str) -> str:
    """Anki's own strip_html - preferred below over the fallback, since it
    handles more edge cases (MathJax, LaTeX, etc.) - is a blind regex
    tag-stripper with NO special handling for block-level tags: checked
    directly against Anki's source (rslib/src/text.rs), it's just
    `HTML.replace_all(html, "")`. <br>/<div>/<p>/<li> are deleted with
    nothing put in their place, jamming adjacent block-level content
    together with zero separation - not only inside this addon's own
    fallback path (which pytest exercises, since Anki isn't installed
    there), but in every real run inside actual Anki too. This runs before
    either strip_html implementation, turning those tags into a literal
    newline so the separation survives regardless of which one ends up
    used. Any <li> that was part of a glossary list has already been
    consumed by _join_glossary_list_items above by the time this runs.

    Also inserts a space before each data-sc-class="tag" span (see above) -
    a lighter separator than the newline used for the other tags here,
    since a run of short labels reads better as one compact line than
    stacked one per line.
    """
    text = _BR_RE.sub("\n", text)
    text = _DIV_OPEN_RE.sub("\n", text)
    text = _P_OPEN_RE.sub("\n", text)
    text = _LI_OPEN_RE.sub("\n", text)
    text = _TAG_SPAN_OPEN_RE.sub(" ", text)
    return text


def _fallback_strip_html(text: str) -> str:
    text = _TAG_RE.sub("", text)
    return html.unescape(text)


def strip_furigana(text: str, keep: str = "base") -> str:
    """Collapse Anki's `base[reading]` furigana syntax to plain text.

    keep="base" keeps the base text (e.g. kanji) and drops the bracketed
    reading - the right choice for an Expression field. keep="reading" keeps
    only the bracketed reading - useful if a Reading field is itself stored
    using this syntax rather than as plain kana.
    """
    if keep == "reading":
        return _FURIGANA_RE.sub(lambda m: m.group(2) or m.group(1), text)
    return _FURIGANA_RE.sub(lambda m: m.group(1), text)


def clean_field(raw: str, strip_furigana_brackets: bool = True, furigana_keep: str = "base") -> str:
    """Clean one Anki field value for use as a Kotoba CSV cell."""
    if not raw:
        return ""

    text = _SOUND_RE.sub("", raw)
    # Always resolved (not gated by strip_furigana_brackets): once <ruby>
    # tags are gone there's no readable fallback the way base[reading] has,
    # so leaving this alone only produces garbled text, never a valid choice.
    text = _resolve_ruby_html(text, keep=furigana_keep)
    text = _join_glossary_list_items(text)
    text = _insert_block_separators(text)
    text = (_anki_strip_html or _fallback_strip_html)(text)

    if strip_furigana_brackets:
        text = strip_furigana(text, keep=furigana_keep)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


_ELLIPSIS = "…"


def truncate_text(text: str, max_length: int) -> str:
    """Cut `text` down to `max_length` characters (ellipsis included) for
    fields like Comment, where mined notes often carry several dictionaries'
    worth of glosses concatenated together - far past what a quiz hint
    should be, and past Kotoba's own length limit. Prefers cutting at the
    last space or newline before the limit so a word (or, after
    format_comment_sections, a dictionary section) isn't split in half, but
    falls back to a hard cut if there's no reasonably-placed break (e.g.
    dense Japanese text with none).
    """
    if max_length <= 0 or len(text) <= max_length:
        return text

    limit = max(max_length - len(_ELLIPSIS), 0)
    cut = text[:limit]
    last_break = max(cut.rfind(" "), cut.rfind("\n"))
    if last_break > limit * 0.6:
        cut = cut[:last_break]
    return cut.rstrip() + _ELLIPSIS


# Mined notes (Yomitan/Jitendex-style) often concatenate several
# dictionaries' worth of glosses into one field with zero separator between
# them, e.g. "...entering through a gateJMdict(大辞林 第四版) にゅうもん...".
# These are the shapes that reliably mark a new dictionary section starting
# in that kind of text, checked against real exports:
#   - "(★, Jitendex.org [2026-01-04])" - Jitendex's own priority/source stamp
#   - "(大辞林 第四版)" / "(新和英大辞典 第5版)" - a Japanese dictionary name
#     followed by an edition marker (第<N>版)
#   - "(JMdict)" or a bare trailing "JMdict" / "JMdict | Tatoeba" - JMdict's
#     ubiquitous attribution, with or without parens
# Deliberately narrow: a generic aside like "(cannot) possibly | (not) by
# any means" (real JMdict gloss text) must NOT match, since full parsing to
# pick a single "right" dictionary was already tried and rejected as too
# fragile - this only ever inserts whitespace, never drops content.
_DICTIONARY_MARKER_RE = re.compile(
    r"\("
    r"(?:"
    r"[^()]*★[^()]*"
    r"|[^()]*(?:https?://|\.(?:org|com|net|edu|io|jp)\b|\[\d{4}-\d{2}-\d{2}\])[^()]*"
    r"|[^()]*第[0-9一二三四五六七八九十]+版[^()]*"
    r"|JMdict"
    r")"
    r"\)"
    r"|JMdict(?:\s*\|\s*Tatoeba)?"
)


# Beyond separating whole dictionary-source blocks (above), a single
# Jitendex-sourced block itself concatenates its own parts - a POS/gloss
# list, an example sentence, its translation, sometimes a second sense's
# gloss list, and a "forms" (alternate spellings) list - with zero
# separator between any of them, e.g. "...to give upforms断つ絶つ" or
# "...guts, OK?characternaturedispositionpersonality". There's no reliable
# way to split the glosses themselves (bare English words glued together,
# e.g. "willpowergutsdeterminationgritspirit", would need a wordlist to
# segment - the same kind of full parsing already rejected as too fragile
# for picking a single dictionary above) - but the boundaries AROUND an
# example sentence and its translation are unambiguous from script and
# punctuation alone, and are worth separating even when the gloss list on
# either side stays run together.
# Deliberately excludes digits: a Latin digit directly touching a kanji is
# routinely normal Japanese typography (edition markers like "第5版", years
# like "2026年", counters like "3つ"), not an English-to-Japanese boundary.
_ASCII_TO_JAPANESE_RE = re.compile(r"(?<=[a-zA-Z)\]])(?=[぀-ヿ一-鿿])")
_JAPANESE_SENTENCE_END_TO_LATIN_CAP_RE = re.compile(r"(?<=[。？！])(?=[A-Z])")
# Excludes the domain suffixes used in the citation stamps above (e.g.
# "Jitendex.org") so this doesn't split those apart.
_LATIN_SENTENCE_END_TO_LOWER_RE = re.compile(r"(?<=[.?!])(?!org\b|com\b|net\b|edu\b|io\b|jp\b)(?=[a-z])")
_GLUED_FORMS_TAG_RE = re.compile(r"(?<=[a-z])(?=forms\b)")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")


def format_comment_sections(text: str) -> str:
    """Insert a newline before each recognized dictionary-source marker (see
    _DICTIONARY_MARKER_RE), then at the unambiguous script/punctuation
    boundaries within a single entry (see the regexes above), so a long
    mined comment reads as distinct sections instead of one run-on wall of
    text. A comment with no recognized markers - or just one, at the very
    start - is returned as-is.
    """
    if not text:
        return text

    def _break_before(match):
        return match.group(0) if match.start() == 0 else "\n" + match.group(0)

    text = _DICTIONARY_MARKER_RE.sub(_break_before, text)
    text = _ASCII_TO_JAPANESE_RE.sub("\n", text)
    text = _JAPANESE_SENTENCE_END_TO_LATIN_CAP_RE.sub("\n", text)
    text = _LATIN_SENTENCE_END_TO_LOWER_RE.sub("\n", text)
    text = _GLUED_FORMS_TAG_RE.sub("\n", text)
    # clean_field's own HTML-structure-based breaks (e.g. a <div> right
    # before a dictionary citation) and the marker-based break just above
    # can both land at the same point - collapse the resulting blank line
    # rather than leave two rules' insertions stacked.
    return _MULTI_NEWLINE_RE.sub("\n", text)
