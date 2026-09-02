"""Minimal duck-typed stand-ins for the bits of anki.notes.Note and
anki.collection.Collection that kotoba/export.py and kotoba/search.py touch.
"""


class FakeNote(dict):
    def __init__(self, note_type_name: str, fields: dict, nid: int = 1):
        super().__init__(fields)
        self.id = nid
        self._note_type_name = note_type_name

    def note_type(self):
        return {"name": self._note_type_name}


class FakeCard:
    def __init__(self, cid: int, nid: int):
        self.id = cid
        self.nid = nid


class FakeCollection:
    """`notes`: dict of nid -> FakeNote, one card per note by default.
    `query_results`: optional dict mapping an exact query string to the list
    of card ids find_cards should return for it; omit to return every card
    for any query (mirrors Anki's own "empty search = everything" behavior).
    """

    def __init__(self, notes: dict, query_results: dict = None):
        self.notes = notes
        self.cards = [FakeCard(cid=nid, nid=nid) for nid in notes]
        self.query_results = query_results

    def find_cards(self, query):
        if self.query_results is not None:
            return self.query_results.get(query, [])
        return [c.id for c in self.cards]

    def get_card(self, cid):
        for c in self.cards:
            if c.id == cid:
                return c
        raise KeyError(cid)

    def get_note(self, nid):
        return self.notes[nid]
