"""Orchestrates a preset: run its search, pull matching notes, map fields,
and produce Kotoba-ready cards plus a rendered deck name.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from . import clean, search
from . import format as kotoba_format

_ANSWER_SPLIT_RE = re.compile(r"[,、]")


@dataclass
class ExportResult:
    cards: list
    deck_name: str
    total_matched_notes: int
    skipped_wrong_note_type: int
    merged_duplicate_count: int = 0
    warnings: list = field(default_factory=list)


def render_deck_name(preset, today=None) -> str:
    today = today or date.today()
    return preset.deck_name_template.format(preset_name=preset.name, date=today.isoformat())


def _field_value(note, field_name: str) -> str:
    if not field_name:
        return ""
    try:
        return note[field_name]
    except (KeyError, IndexError):
        return ""


def _note_type_name(note) -> str:
    nt = note.note_type()
    return nt["name"] if nt else ""


def build_query_for_preset(preset) -> str:
    filters = search.QueryFilters(
        forgotten_today=preset.forgotten_today,
        leech=preset.leech,
        suspended=preset.suspended,
        due=preset.due,
        tags=list(preset.tags),
        deck=preset.deck,
        raw_query=preset.raw_query,
    )
    return search.build_query(filters)


def build_cards_for_preset(col, preset) -> ExportResult:
    """`col` is an Anki Collection (or a duck-typed fake exposing find_cards,
    get_card, get_note - see tests/ for the fake used in unit tests).
    """
    query = build_query_for_preset(preset)
    note_ids = search.find_matching_note_ids(col, query)

    cards = []
    skipped = 0
    for nid in note_ids:
        note = col.get_note(nid)
        mapping = preset.field_mapping_for(_note_type_name(note))
        if mapping is None:
            skipped += 1
            continue

        values = {}
        for key, mapping_key in (
            ("expression", "expression_field"),
            ("reading", "reading_field"),
            ("meaning", "meaning_field"),
        ):
            raw = _field_value(note, mapping.get(mapping_key, ""))
            furigana_keep = "reading" if key == "reading" else "base"
            values[key] = clean.clean_field(
                raw,
                strip_furigana_brackets=preset.strip_furigana_brackets,
                furigana_keep=furigana_keep,
            )

        question = values.get(preset.question_source, "")
        answer_text = values.get(preset.answer_source, "")
        comment = "" if preset.comment_source == "none" else values.get(preset.comment_source, "")
        comment = clean.format_comment_sections(comment)
        comment = clean.truncate_text(comment, min(preset.comment_max_length, kotoba_format.COMMENT_MAX_LENGTH))
        answers = [a.strip() for a in _ANSWER_SPLIT_RE.split(answer_text) if a.strip()]

        cards.append(
            kotoba_format.KotobaCard(
                question=question,
                answers=answers,
                comment=comment,
                instructions=preset.instructions,
                render_as=preset.render_as,
                source_note_ids=[nid],
            )
        )

    merged_cards = kotoba_format.merge_duplicate_questions(cards)
    warnings = kotoba_format.validate_cards(merged_cards)
    return ExportResult(
        cards=merged_cards,
        deck_name=render_deck_name(preset),
        total_matched_notes=len(note_ids),
        skipped_wrong_note_type=skipped,
        merged_duplicate_count=len(cards) - len(merged_cards),
        warnings=warnings,
    )
