"""A small local record of past export runs - what got exported, when, and
how it went - so you can tell at a glance whether an automatic run actually
did anything, without having to remember to check. Stored in the same
config dict as presets/settings, capped at MAX_ENTRIES so it stays "small".
"""
import csv
import dataclasses
import io
from dataclasses import asdict, dataclass
from datetime import datetime

MAX_ENTRIES = 200

OUTCOME_COPIED = "copied"
OUTCOME_SAVED = "saved"
OUTCOME_UPLOADED = "uploaded"
OUTCOME_NO_CARDS = "no_cards"
OUTCOME_SKIPPED = "skipped"  # deliberately not run (e.g. unattended safety check failed)
OUTCOME_ERROR = "error"

TRIGGER_MANUAL = "manual"
# Same string values as presets.AUTO_RUN_STARTUP/AUTO_RUN_SHUTDOWN/
# AUTO_RUN_SYNC on purpose, so a trigger value can be passed straight into
# both Preset.matches_auto_trigger() and history.new_entry() with no
# translation.
TRIGGER_AUTO_STARTUP = "startup"
TRIGGER_AUTO_SHUTDOWN = "shutdown"
TRIGGER_AUTO_SYNC = "sync"


@dataclass
class HistoryEntry:
    timestamp: str
    preset_name: str
    deck_name: str
    card_count: int
    outcome: str
    triggered_by: str = TRIGGER_MANUAL
    detail: str = ""
    # Wall-clock time the logged action itself took, in seconds - for a
    # manual copy/save/upload that's just that one action (not however long
    # the preview dialog happened to sit open first); for an automatic
    # run it's search+build+upload combined, since that's the part that can
    # actually delay Anki's own startup/shutdown. 0.0 for outcomes where
    # nothing timed actually ran (e.g. a deliberate skip).
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "HistoryEntry":
        known = {f.name for f in dataclasses.fields(HistoryEntry)}
        return HistoryEntry(**{k: v for k, v in d.items() if k in known})


def new_entry(
    preset_name: str,
    deck_name: str,
    card_count: int,
    outcome: str,
    triggered_by: str = TRIGGER_MANUAL,
    detail: str = "",
    duration_seconds: float = 0.0,
    now: datetime = None,
) -> HistoryEntry:
    return HistoryEntry(
        timestamp=(now or datetime.now()).isoformat(timespec="seconds"),
        preset_name=preset_name,
        deck_name=deck_name,
        card_count=card_count,
        outcome=outcome,
        triggered_by=triggered_by,
        detail=detail,
        duration_seconds=round(duration_seconds, 2),
    )


def load_history(config: dict) -> list:
    return [HistoryEntry.from_dict(e) for e in config.get("history", [])]


def append_entry(config: dict, entry: HistoryEntry) -> dict:
    entries = load_history(config)
    entries.append(entry)
    entries = entries[-MAX_ENTRIES:]
    config["history"] = [e.to_dict() for e in entries]
    return config


def clear_history(config: dict) -> dict:
    config["history"] = []
    return config


CSV_HEADER_ROW = ["Timestamp", "Preset", "Deck", "Cards", "Outcome", "Trigger", "Duration (s)", "Detail"]


def history_to_csv(entries: list) -> str:
    """Serialize history entries to CSV, for taking a copy of the log out of
    Anki (e.g. into a spreadsheet) - same idea as presets_to_json, but for
    the history log. Written in the order given; callers wanting
    chronological order should pass load_history()'s result as-is (oldest
    first) rather than the History dialog's reversed (newest-first) display
    order.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_HEADER_ROW)
    for entry in entries:
        writer.writerow(
            [
                entry.timestamp,
                entry.preset_name,
                entry.deck_name,
                entry.card_count,
                entry.outcome,
                entry.triggered_by,
                entry.duration_seconds,
                entry.detail,
            ]
        )
    return buf.getvalue()
