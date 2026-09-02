"""Builds the CSV that Kotoba's custom-deck importer expects, and the
matching deck-level metadata, using the exact field limits from Kotoba's own
validation code (mistval/kotoba, common/deck_validation.js + node-common
constants) so a bad export gets caught locally instead of by a confusing
rejection on kotobaweb.com.
"""
import csv
import io
import re
from dataclasses import dataclass, field

HEADER_ROW = ["Question", "Answers", "Comment", "Instructions", "Render as"]
RENDER_AS_TEXT = "TEXT"
RENDER_AS_IMAGE = "IMAGE"
BOM = "﻿"

# Limits mirrored from mistval/kotoba's common/deck_validation.js and
# node-common/constants.js (checked 2026-09-01). Kotoba renders IMAGE
# questions from plain text too (no URL needed) - it's the "hide the kanji
# from copy/paste" mode reading-practice decks use, hence the much shorter
# question length cap than TEXT gets.
FULL_NAME_MAX_LENGTH = 60
SHORT_NAME_MAX_LENGTH = 25
DESCRIPTION_MAX_LENGTH = 500
INSTRUCTIONS_MAX_LENGTH = 400
TEXT_QUESTION_MAX_LENGTH = 400
IMAGE_QUESTION_MAX_LENGTH = 20
ANSWERS_TOTAL_MAX_LENGTH = 200
COMMENT_MAX_LENGTH = 600
MAX_CARDS = 10000
SHORT_NAME_ALLOWED_CHARACTERS_REGEX = re.compile(r"^[a-z0-9_]{1,25}$")

_QUESTION_MAX_LENGTH_BY_STRATEGY = {
    RENDER_AS_TEXT: TEXT_QUESTION_MAX_LENGTH,
    "TEXT_WITH_HINT": TEXT_QUESTION_MAX_LENGTH,
    RENDER_AS_IMAGE: IMAGE_QUESTION_MAX_LENGTH,
    "IMAGE_WITH_HINT": IMAGE_QUESTION_MAX_LENGTH,
}

_SHORT_NAME_DISALLOWED_RE = re.compile(r"[^a-z0-9_]+")


@dataclass
class KotobaCard:
    question: str
    answers: list = field(default_factory=list)
    comment: str = ""
    instructions: str = ""
    render_as: str = RENDER_AS_TEXT
    # Anki note id(s) this card came from - not sent to Kotoba (build_csv and
    # api.py's payload builder both list their fields explicitly), just kept
    # for "open in Browser" from the export preview. A merged card (see
    # merge_duplicate_questions) can trace back to more than one note.
    source_note_ids: list = field(default_factory=list)

    def answers_joined(self) -> str:
        return ",".join(a for a in self.answers if a)


def make_short_name(full_name: str) -> str:
    """Derive a valid Kotoba deck short-name (its URL slug) from a display name."""
    lowered = full_name.strip().lower()
    slug = _SHORT_NAME_DISALLOWED_RE.sub("_", lowered).strip("_")
    if not slug:
        slug = "deck"
    return slug[:SHORT_NAME_MAX_LENGTH]


def merge_duplicate_questions(cards: list) -> list:
    """Kotoba rejects a whole deck if two cards share the same question, so
    merge such cards into one: union their answers (e.g. 表 read as either
    ひょう or おもて becomes one card accepting both) and join distinct,
    non-empty comments. Cards with a blank question are left un-merged with
    each other, since merging those would just hide how many there are -
    they already get flagged as empty by validate_cards.
    """
    merged_by_key = {}
    order = []
    blank_counter = 0

    for card in cards:
        key = card.question
        if not key.strip():
            blank_counter += 1
            key = f"\0blank{blank_counter}"

        existing = merged_by_key.get(key)
        if existing is None:
            merged_by_key[key] = KotobaCard(
                question=card.question,
                answers=list(dict.fromkeys(a for a in card.answers if a)),
                comment=card.comment,
                instructions=card.instructions,
                render_as=card.render_as,
                source_note_ids=list(card.source_note_ids),
            )
            order.append(key)
        else:
            for answer in card.answers:
                if answer and answer not in existing.answers:
                    existing.answers.append(answer)
            if card.comment and card.comment not in existing.comment:
                existing.comment = f"{existing.comment} / {card.comment}" if existing.comment else card.comment
            for nid in card.source_note_ids:
                if nid not in existing.source_note_ids:
                    existing.source_note_ids.append(nid)

    return [merged_by_key[key] for key in order]


_CITATION_LIKE_RE = re.compile(
    r"https?://"  # a URL
    r"|\.(?:org|com|net|edu|io|jp)\b"  # a domain-looking suffix
    r"|\[\d{4}-\d{2}-\d{2}\]"  # a bracketed ISO date, e.g. dictionary source stamps
)


def looks_like_citation(text: str) -> bool:
    """Flags text that looks like a dictionary source citation (e.g.
    "Jitendex.org [2026-01-04]") rather than an actual reading/expression.
    Mining tools occasionally leave this in the wrong field when they fail
    to resolve a clean reading for a word - this catches it before export
    instead of surfacing it live in a quiz.
    """
    return bool(text) and bool(_CITATION_LIKE_RE.search(text))


def validate_cards(cards: list) -> list:
    """Return a list of human-readable warning strings for anything that
    would be rejected (or silently truncated) by Kotoba. Empty list = clean.
    """
    warnings = []
    if len(cards) > MAX_CARDS:
        warnings.append(f"{len(cards)} cards exceeds Kotoba's limit of {MAX_CARDS}.")

    seen_questions = {}
    for i, card in enumerate(cards, start=1):
        if card.question.strip():
            first_seen = seen_questions.setdefault(card.question, i)
            if first_seen != i:
                warnings.append(
                    f"Card {i}: question \"{card.question}\" duplicates card {first_seen} - "
                    "Kotoba rejects decks with duplicate questions."
                )

    for i, card in enumerate(cards, start=1):
        label = f"Card {i}"
        question_max_length = _QUESTION_MAX_LENGTH_BY_STRATEGY.get(card.render_as, TEXT_QUESTION_MAX_LENGTH)
        if not card.question.strip():
            warnings.append(f"{label}: empty question - it will be skipped.")
        elif len(card.question) > question_max_length:
            warnings.append(
                f"{label}: question is {len(card.question)} chars, "
                f"over Kotoba's {question_max_length} limit for {card.render_as} questions."
            )
        answers_len = len(card.answers_joined())
        if not card.answers or not any(a.strip() for a in card.answers):
            warnings.append(f"{label}: empty answer - it will be skipped.")
        elif answers_len > ANSWERS_TOTAL_MAX_LENGTH:
            warnings.append(
                f"{label}: answers total {answers_len} chars, "
                f"over Kotoba's {ANSWERS_TOTAL_MAX_LENGTH} limit."
            )

        if looks_like_citation(card.question):
            warnings.append(
                f'{label}: question "{card.question}" looks like a dictionary source citation, '
                "not a real expression - check this note's field mapping."
            )
        for answer in card.answers:
            if looks_like_citation(answer):
                warnings.append(
                    f'{label}: answer "{answer}" looks like a dictionary source citation, '
                    "not a real reading - check this note's field mapping."
                )
        if len(card.comment) > COMMENT_MAX_LENGTH:
            warnings.append(
                f"{label}: comment is {len(card.comment)} chars, "
                f"over Kotoba's {COMMENT_MAX_LENGTH} limit."
            )
        if len(card.instructions) > INSTRUCTIONS_MAX_LENGTH:
            warnings.append(
                f"{label}: instructions is {len(card.instructions)} chars, "
                f"over Kotoba's {INSTRUCTIONS_MAX_LENGTH} limit."
            )
    return warnings


def build_csv(cards: list) -> str:
    """Build Kotoba's native custom-deck CSV: header row, comma-delimited,
    leading BOM (matching Kotoba's own exporter so the import round-trips).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(HEADER_ROW)
    for card in cards:
        writer.writerow(
            [
                card.question,
                card.answers_joined(),
                card.comment,
                card.instructions,
                card.render_as,
            ]
        )
    return BOM + buf.getvalue()
