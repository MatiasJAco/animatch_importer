from .fetcher import Fetcher, SEASONS
from .importer import Importer

class Sync:
    def __init__(self, fetcher: Fetcher, importer: Importer):
        self.fetcher = fetcher
        self.importer = importer

    def run(self, year, people_limit=100, refresh=False):
        # Phase 1: all network activity. Existing raw files are reused.
        self.fetcher.top_people_voices(people_limit, refresh)
        self.fetcher.seasons(year, SEASONS, refresh)

        # Phase 2: no network activity. PostgreSQL is populated from local files.
        self.importer.import_top_people(people_limit)
        return self.importer.import_year(year, SEASONS)
