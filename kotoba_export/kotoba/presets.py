"""Preset data model + CRUD against the addon's config dict.

A preset bundles: which cards to pull (quick-filter chips + tags + a raw
Anki search string), which note type and fields they come from, how those
fields map onto Kotoba's Question/Answers/Comment columns, and how the
resulting deck should be named/reused on Kotoba.
"""
import dataclasses
import json
import uuid
from dataclasses import asdict, dataclass, field

DEFAULT_INSTRUCTIONS = "Type the reading!"
DEFAULT_DECK_NAME_TEMPLATE = "{preset_name} - {date}"

REUSE_NEW_EACH_TIME = "new_each_time"
REUSE_OVERWRITE = "overwrite"

AUTO_RUN_STARTUP = "startup"
AUTO_RUN_SHUTDOWN = "shutdown"
AUTO_RUN_SYNC = "sync"
ALL_AUTO_RUN_TRIGGERS = (AUTO_RUN_STARTUP, AUTO_RUN_SHUTDOWN, AUTO_RUN_SYNC)

# Legacy value from before auto_run_triggers existed ("off" needed no
# constant - _migrate_legacy_auto_run_field's else branch already covers
# it and anything else unrecognized), kept only so
# _migrate_legacy_auto_run_field can recognize and translate it.
_LEGACY_AUTO_RUN_BOTH = "both"


def _migrate_legacy_note_type_fields(d: dict) -> dict:
    """Presets saved before multi-note-type support stored a single
    note_type plus expression_field/reading_field/meaning_field. Fold those
    into a one-entry note_type_mappings dict so existing presets keep
    working unchanged. No-op if note_type_mappings is already present, or
    there's no legacy note_type to migrate.
    """
    if "note_type_mappings" in d or not d.get("note_type"):
        return d
    d = dict(d)
    d["note_type_mappings"] = {
        d["note_type"]: {
            "expression_field": d.get("expression_field", ""),
            "reading_field": d.get("reading_field", ""),
            "meaning_field": d.get("meaning_field", ""),
        }
    }
    return d


def _migrate_legacy_auto_run_field(d: dict) -> dict:
    """Presets saved before the sync trigger existed stored a single
    auto_run string ("off"/"startup"/"shutdown"/"both") rather than a list
    of triggers - a single-value enum stopped scaling once there was a
    third independent trigger to combine. Fold that into the new
    auto_run_triggers list so existing presets keep their setting
    unchanged. No-op if auto_run_triggers is already present, or there's no
    legacy auto_run to migrate.
    """
    if "auto_run_triggers" in d or "auto_run" not in d:
        return d
    d = dict(d)
    legacy = d["auto_run"]
    if legacy == _LEGACY_AUTO_RUN_BOTH:
        d["auto_run_triggers"] = [AUTO_RUN_STARTUP, AUTO_RUN_SHUTDOWN]
    elif legacy in (AUTO_RUN_STARTUP, AUTO_RUN_SHUTDOWN):
        d["auto_run_triggers"] = [legacy]
    else:
        d["auto_run_triggers"] = []
    return d


@dataclass
class Preset:
    id: str
    name: str

    # Quick-filter chips, AND-ed together with tags/deck/raw_query.
    forgotten_today: bool = False
    leech: bool = False
    suspended: bool = False
    due: bool = False
    tags: list = field(default_factory=list)
    deck: str = ""  # "" = any deck; otherwise also matches its subdecks
    raw_query: str = ""

    # {note_type_name: {"expression_field": ..., "reading_field": ...,
    # "meaning_field": ...}}. A matched note whose type isn't a key here is
    # skipped (counted in ExportResult.skipped_wrong_note_type) - lets one
    # preset pull from several note types (e.g. different mining setups),
    # each with its own field names, instead of needing a separate preset
    # per note type.
    note_type_mappings: dict = field(default_factory=dict)

    # Which concept feeds which Kotoba CSV column. "none" for comment_source
    # means the Comment column is left blank.
    question_source: str = "expression"
    answer_source: str = "reading"
    comment_source: str = "meaning"

    strip_furigana_brackets: bool = True
    # Mined notes (Yomitan/JPDB-style) often stuff several dictionaries'
    # worth of glosses into one field - way past what a quiz hint needs, and
    # past Kotoba's own 600-char Comment cap. Comment text gets cut to this
    # length (word-boundary aware) before export; export.py additionally
    # clamps it to Kotoba's real limit regardless of what's set here.
    comment_max_length: int = 300
    # "IMAGE" renders the question as a picture Kotoba generates from the
    # text - the convention reading-practice decks use so the kanji can't be
    # copy/pasted into a translator, defeating the point of "type the
    # reading". "TEXT" shows it as selectable text instead.
    render_as: str = "IMAGE"
    instructions: str = DEFAULT_INSTRUCTIONS
    deck_name_template: str = DEFAULT_DECK_NAME_TEMPLATE
    deck_description: str = ""
    # "overwrite" links by the *rendered deck name*, not just "this preset":
    # running with the same name PATCHes the same Kotoba deck; typing a
    # different name at export time (in the preview dialog) creates a new,
    # separate deck instead of touching the old one. So a template that
    # includes {date} still makes a fresh deck every day even in overwrite
    # mode - drop {date} from the template for a single deck that keeps
    # getting replaced.
    deck_reuse_mode: str = REUSE_NEW_EACH_TIME

    # Subset of ALL_AUTO_RUN_TRIGGERS ("startup"/"shutdown"/"sync"): runs
    # this preset unattended via direct-API upload (there's no one there to
    # click Upload) whenever any checked trigger fires - Anki opening,
    # closing, or finishing an AnkiWeb sync. Empty list = never runs
    # automatically. Requires advanced mode AND the global auto-export
    # switch (config["advanced"]["auto_export_enabled"]) to both be on -
    # this field alone does not enable anything.
    auto_run_triggers: list = field(default_factory=list)

    # deck_links: {rendered_deck_name: {"id": ..., "secret": ...}},
    # populated after a successful direct-API export in overwrite mode so a
    # later run with that same name knows which Kotoba deck to PATCH.
    deck_links: dict = field(default_factory=dict)

    # {rendered_deck_name: sha256 hex fingerprint of the card content (see
    # kotoba/format.py's cards_fingerprint) last successfully uploaded
    # there} - independent of deck_links (applies in "new each time" mode
    # too, where there's no deck_links entry at all). Lets an automatic
    # sync-triggered export skip a redundant re-upload when nothing has
    # actually changed since the last successful upload, manual or
    # automatic.
    last_upload_hashes: dict = field(default_factory=dict)

    @staticmethod
    def new(name: str) -> "Preset":
        return Preset(id=str(uuid.uuid4()), name=name)

    def duplicate(self, new_name: str = None) -> "Preset":
        """A copy of this preset with a fresh id and no deck_links - those
        are tied to the original's identity via its rendered deck name, so a
        clone should not silently start overwriting the original's Kotoba
        deck the first time it's run in overwrite mode. Everything else
        (search filters, field mappings, Kotoba column mapping, deck naming)
        is copied as-is.
        """
        data = self.to_dict()
        data["id"] = str(uuid.uuid4())
        data["name"] = new_name if new_name is not None else f"{self.name} (copy)"
        data["deck_links"] = {}
        data["last_upload_hashes"] = {}
        return Preset.from_dict(data)

    def matches_auto_trigger(self, trigger: str) -> bool:
        """trigger: AUTO_RUN_STARTUP, AUTO_RUN_SHUTDOWN, or AUTO_RUN_SYNC.
        True if this preset is set to run unattended for that trigger."""
        return trigger in self.auto_run_triggers

    def get_deck_link(self, deck_name: str):
        """Returns {"id": ..., "secret": ...} for a previously-uploaded deck
        with this exact rendered name, or None if none exists yet."""
        return self.deck_links.get(deck_name)

    def set_deck_link(self, deck_name: str, deck_id: str, readwrite_secret: str) -> None:
        self.deck_links[deck_name] = {"id": deck_id, "secret": readwrite_secret}

    def get_last_upload_hash(self, deck_name: str):
        return self.last_upload_hashes.get(deck_name)

    def set_last_upload_hash(self, deck_name: str, fingerprint: str) -> None:
        self.last_upload_hashes[deck_name] = fingerprint

    def field_mapping_for(self, note_type_name: str):
        """Returns {"expression_field": ..., "reading_field": ..., "meaning_field": ...}
        for this note type, or None if the preset doesn't map it (such a
        note gets skipped during export)."""
        return self.note_type_mappings.get(note_type_name)

    def set_field_mapping(
        self, note_type_name: str, expression_field: str, reading_field: str, meaning_field: str
    ) -> None:
        self.note_type_mappings[note_type_name] = {
            "expression_field": expression_field,
            "reading_field": reading_field,
            "meaning_field": meaning_field,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Preset":
        d = _migrate_legacy_note_type_fields(d)
        d = _migrate_legacy_auto_run_field(d)
        known = {f.name for f in dataclasses.fields(Preset)}
        return Preset(**{k: v for k, v in d.items() if k in known})


def load_presets(config: dict) -> list:
    return [Preset.from_dict(p) for p in config.get("presets", [])]


def load_presets_safe(config: dict) -> tuple:
    """Like load_presets, but never raises - returns ([], "") normally, or
    ([], error_message) if a preset entry is malformed (e.g. missing id/name,
    or not a dict at all - both raise inside Preset.from_dict). Intended for
    callers registered as Anki gui_hooks callbacks (see __init__.py's
    _run_auto_presets), which must never let an exception escape - a
    corrupted config would otherwise take down Anki's own
    startup/shutdown/sync sequence instead of just failing this feature.
    """
    try:
        return load_presets(config), ""
    except Exception as exc:  # noqa: BLE001 - see docstring
        return [], str(exc)


def sanitize_imported_presets(presets: list) -> list:
    """Resets auto_run_triggers and deck_links on each preset - the two
    fields with real-world side effects (unattended uploads, and which live
    Kotoba deck a name gets linked to) - since an imported file is untrusted
    input: it may have been shared by someone else, not just a self-backup,
    and importing shouldn't be able to silently wire up automatic uploads or
    rebind an existing deck link. Mutates the given presets in place and
    returns the same list, for convenience at the call site.
    """
    for preset in presets:
        preset.auto_run_triggers = []
        preset.deck_links = {}
    return presets


def save_presets(config: dict, presets: list) -> dict:
    config["presets"] = [p.to_dict() for p in presets]
    return config


def upsert_preset(config: dict, preset: Preset) -> dict:
    presets = load_presets(config)
    for i, existing in enumerate(presets):
        if existing.id == preset.id:
            presets[i] = preset
            break
    else:
        presets.append(preset)
    return save_presets(config, presets)


def delete_preset(config: dict, preset_id: str) -> dict:
    presets = [p for p in load_presets(config) if p.id != preset_id]
    return save_presets(config, presets)


def presets_to_json(presets: list) -> str:
    """Serialize presets for backup/transfer to another machine. Note this
    carries field/note-type *names*, not Anki's internal ids - they won't
    resolve on a collection where those names don't exist, which is the
    caller's job to warn about after import.
    """
    return json.dumps([p.to_dict() for p in presets], indent=2, ensure_ascii=False)


def presets_from_json(text: str) -> list:
    """Inverse of presets_to_json. Raises ValueError on anything malformed
    (not a JSON array, an entry missing id/name) so callers can show one
    clear message instead of a raw traceback."""
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of presets.")

    presets = []
    for i, entry in enumerate(data, start=1):
        if not isinstance(entry, dict) or "id" not in entry or "name" not in entry:
            raise ValueError(f"Entry {i} is missing required fields (id, name).")
        presets.append(Preset.from_dict(entry))
    return presets
