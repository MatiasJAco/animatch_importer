from pathlib import Path
from .client import TenraiClient
from .storage import RawStore

SEASONS = ("winter", "spring", "summer", "fall")

class Fetcher:
    def __init__(self, client: TenraiClient, store: RawStore):
        self.client = client
        self.store = store

    def top_people(self, limit=100, refresh=False):
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        remaining = limit
        page = 1
        fetched = 0
        while remaining:
            per_page = min(50, remaining)
            rel = f"top_people/pages/page-{page:04d}-limit-{per_page}.json"
            payload, made = self.store.fetch_once(
                self.client, rel, "/top/people", {"page": page, "limit": per_page}, refresh
            )
            people = payload.get("data", [])
            if not people:
                break
            for person in people:
                pid = person.get("mal_id")
                if not pid:
                    continue
                self.store.fetch_once(
                    self.client, f"people/{pid}/full.json", f"/people/{pid}/full", refresh=refresh
                )
                self.store.fetch_once(
                    self.client, f"people/{pid}/voices/pages/page-0001.json", f"/people/{pid}/voices", refresh=refresh
                )
            fetched += len(people)
            remaining -= len(people)
            if not payload.get("pagination", {}).get("has_next_page"):
                break
            page += 1
        return fetched

    def _fetch_paginated(self, endpoint, rel_dir, refresh=False):
        page = 1
        total = 0
        while True:
            rel = f"{rel_dir}/page-{page:04d}.json"
            payload, _ = self.store.fetch_once(
                self.client, rel, endpoint, {"page": page}, refresh
            )
            total += len(payload.get("data", []))
            if not payload.get("pagination", {}).get("has_next_page"):
                break
            page += 1
        return total

    def person_voices(self, person_id, refresh=False):
        return self._fetch_paginated(
            f"/people/{person_id}/voices", f"people/{person_id}/voices", refresh
        )

    def top_people_voices(self, limit=100, refresh=False):
        self.top_people(limit, refresh)
        pages = list(self.store.root.glob("top_people/pages/page-*.json"))
        people = []
        for page in pages:
            people.extend(self.store.read_json(str(page.relative_to(self.store.root))).get("data", []))
        people = people[:limit]
        for person in people:
            pid = person.get("mal_id")
            if pid:
                self.person_voices(pid, refresh)

    def season(self, year, season, refresh=False):
        if season not in SEASONS:
            raise ValueError(f"Invalid season: {season}")
        page = 1
        anime_count = 0
        while True:
            rel = f"seasons/{year}/{season}/pages/page-{page:04d}.json"
            payload, _ = self.store.fetch_once(
                self.client, rel, f"/seasons/{year}/{season}", {"page": page}, refresh
            )
            anime_list = payload.get("data", [])
            for anime in anime_list:
                aid = anime.get("mal_id")
                if aid:
                    self.store.fetch_once(
                        self.client,
                        f"seasons/{year}/{season}/anime/{aid}/characters.json",
                        f"/anime/{aid}/characters",
                        refresh=refresh,
                    )
            anime_count += len(anime_list)
            if not payload.get("pagination", {}).get("has_next_page"):
                break
            page += 1
        return anime_count

    def seasons(self, year, seasons=SEASONS, refresh=False):
        total = 0
        for season in seasons:
            total += self.season(year, season, refresh)
        return total
