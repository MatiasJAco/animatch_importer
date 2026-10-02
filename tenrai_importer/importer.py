import json
from pathlib import Path
from .db import Database
from .storage import RawStore

SEASONS = ("winter", "spring", "summer", "fall")

class Importer:
    def __init__(self, db: Database, store: RawStore):
        self.db = db
        self.store = store

    def _json(self, path: Path):
        return self.store.read_json(str(path.relative_to(self.store.root)))

    def import_top_people(self, limit=100):
        run = self.db.run_start(f"import:top_people:{limit}")
        written = 0
        try:
            pages = sorted((self.store.root / "top_people/pages").glob("page-*.json"))
            people = []
            for page in pages:
                people.extend(self._json(page).get("data", []))
            people = people[:limit]
            for person in people:
                pid = person.get("mal_id")
                if not pid:
                    continue
                full_path = self.store.root / f"people/{pid}/full.json"
                full = self._json(full_path).get("data") if full_path.exists() else person
                voices_dir = self.store.root / f"people/{pid}/voices"
                with self.db.transaction():
                    self.db.upsert_person(full or person)
                    if voices_dir.exists():
                        for page in sorted(voices_dir.glob("page-*.json")):
                            for row in self._json(page).get("data", []):
                                self._import_voice_row(pid, row)
                written += 1
            self.db.run_finish(run, "success", 0, written)
            return written
        except Exception as exc:
            self.db.run_finish(run, "failed", 0, written, f"{type(exc).__name__}: {exc}")
            raise

    def _import_voice_row(self, person_id, row):
        character = row.get("character") or {}
        anime = row.get("anime") or {}
        if not character.get("mal_id") or not anime.get("mal_id"):
            return
        self.db.upsert_anime(anime)
        self.db.upsert_character(character)
        self.db.upsert_role(person_id, character["mal_id"], anime["mal_id"], row.get("language"), row.get("role"), row)

    def import_season(self, year, season):
        if season not in SEASONS:
            raise ValueError(f"Invalid season: {season}")
        run = self.db.run_start(f"import:season:{year}:{season}")
        written = 0
        try:
            base = self.store.root / f"seasons/{year}/{season}"
            pages = sorted((base / "pages").glob("page-*.json"))
            for page in pages:
                for anime in self._json(page).get("data", []):
                    aid = anime.get("mal_id")
                    if not aid:
                        continue
                    chars_path = base / f"anime/{aid}/characters.json"
                    with self.db.transaction():
                        self.db.upsert_anime(anime)
                        self.db.link_season(aid, year, season)
                        if chars_path.exists():
                            payload = self._json(chars_path)
                            for entry in payload.get("data", []):
                                character = entry.get("character") or {}
                                if not character.get("mal_id"):
                                    continue
                                self.db.upsert_character(character)
                                for va in entry.get("voice_actors", []):
                                    person = va.get("person") or {}
                                    if not person.get("mal_id"):
                                        continue
                                    self.db.upsert_person(person)
                                    self.db.upsert_role(person["mal_id"], character["mal_id"], aid,
                                                         va.get("language"), entry.get("role"), entry)
                    written += 1
            self.db.run_finish(run, "success", 0, written)
            return written
        except Exception as exc:
            self.db.run_finish(run, "failed", 0, written, f"{type(exc).__name__}: {exc}")
            raise

    def import_year(self, year, seasons=SEASONS):
        total = 0
        for season in seasons:
            total += self.import_season(year, season)
        return total
