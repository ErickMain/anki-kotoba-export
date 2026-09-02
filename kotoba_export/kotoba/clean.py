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


def _fallback_strip_html(text: str) -> str:
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("<div>", "\n").replace("</div>", "")
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


def format_comment_sections(text: str) -> str:
    """Insert a newline before each recognized dictionary-source marker (see
    _DICTIONARY_MARKER_RE) so a long mined comment reads as distinct
    dictionary entries instead of one run-on wall of text. A comment with no
    recognized markers - or just one, at the very start - is returned as-is.
    """
    if not text:
        return text

    def _break_before(match):
        return match.group(0) if match.start() == 0 else "\n" + match.group(0)

    return _DICTIONARY_MARKER_RE.sub(_break_before, text)
