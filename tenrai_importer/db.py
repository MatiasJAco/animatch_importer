import json
from datetime import datetime
import re
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"

def normalize_timestamptz(value):
    """Normalize Tenrai/MAL date values before binding to PostgreSQL TIMESTAMPTZ.

    MAL/Tenrai can return partial dates such as YYYY-MM. PostgreSQL cannot cast
    those directly to timestamptz, so interpret YYYY-MM as the first day of the
    month and YYYY as January 1. Full ISO timestamps/dates are preserved.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return value
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return f"{value}-01"
    if re.fullmatch(r"\d{4}", value):
        return f"{value}-01-01"
    # Normalize a trailing UTC Z to an ISO offset understood by PostgreSQL.
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value

class Database:
    def __init__(self, dsn):
        self.conn = psycopg.connect(dsn, row_factory=dict_row)

    def close(self):
        self.conn.close()

    def init_schema(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute(SCHEMA.read_text())
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    @contextmanager
    def transaction(self):
        try:
            with self.conn.transaction():
                yield
        except Exception:
            # psycopg rolls back the transaction context, but make the
            # connection explicitly clean for subsequent diagnostic SQL.
            self.conn.rollback()
            raise

    def run_start(self, job_name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("INSERT INTO import_runs(job_name) VALUES (%s) RETURNING id", (job_name,))
                run_id = cur.fetchone()["id"]
            self.conn.commit()
            return run_id
        except Exception:
            self.conn.rollback()
            raise

    def run_finish(self, run_id, status, requests_made, records_written, error=None):
        # This method must work even after the import transaction failed.
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE import_runs SET finished_at=now(), status=%s,
                   requests_made=%s, records_written=%s, error=%s WHERE id=%s""",
                (status, requests_made, records_written, error, run_id),
            )
        self.conn.commit()

    def upsert_person(self, p):
        images = p.get("images") or {}
        image_url = ((images.get("jpg") or {}).get("image_url") if isinstance(images, dict) else None)
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO people
                (mal_id,name,given_name,family_name,alternate_names,birthday,website_url,mal_url,
                 image_url,favorites,about,raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(mal_id) DO UPDATE SET
                 name=EXCLUDED.name,given_name=EXCLUDED.given_name,family_name=EXCLUDED.family_name,
                 alternate_names=EXCLUDED.alternate_names,birthday=EXCLUDED.birthday,
                 website_url=EXCLUDED.website_url,mal_url=EXCLUDED.mal_url,image_url=EXCLUDED.image_url,
                 favorites=EXCLUDED.favorites,about=EXCLUDED.about,raw_json=EXCLUDED.raw_json,updated_at=now()""",
                (p["mal_id"],p.get("name") or f"MAL {p['mal_id']}",p.get("given_name"),p.get("family_name"),
                 json.dumps(p.get("alternate_names",[])),normalize_timestamptz(p.get("birthday")),p.get("website_url"),p.get("url"),
                 image_url,p.get("favorites"),p.get("about"),json.dumps(p)))

    def upsert_anime(self, a):
        images = a.get("images") or {}
        image_url = ((images.get("jpg") or {}).get("image_url") if isinstance(images, dict) else None)
        aired = a.get("aired") if isinstance(a.get("aired"), dict) else {}
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO anime
                (mal_id,title,title_english,title_japanese,type,source,episodes,status,aired_from,aired_to,
                 season,year,image_url,mal_url,raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(mal_id) DO UPDATE SET
                 title=EXCLUDED.title,title_english=EXCLUDED.title_english,title_japanese=EXCLUDED.title_japanese,
                 type=EXCLUDED.type,source=EXCLUDED.source,episodes=EXCLUDED.episodes,status=EXCLUDED.status,
                 aired_from=EXCLUDED.aired_from,aired_to=EXCLUDED.aired_to,season=EXCLUDED.season,year=EXCLUDED.year,
                 image_url=EXCLUDED.image_url,mal_url=EXCLUDED.mal_url,raw_json=EXCLUDED.raw_json,updated_at=now()""",
                (a["mal_id"],a.get("title") or f"MAL {a['mal_id']}",a.get("title_english"),a.get("title_japanese"),
                 a.get("type"),a.get("source"),a.get("episodes"),a.get("status"),normalize_timestamptz(aired.get("from")),normalize_timestamptz(aired.get("to")),
                 a.get("season"),a.get("year"),image_url,a.get("url"),json.dumps(a)))

    def upsert_character(self, c):
        images = c.get("images") or {}
        image_url = ((images.get("jpg") or {}).get("image_url") if isinstance(images, dict) else None)
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO characters
                (mal_id,name,name_kanji,image_url,mal_url,raw_json)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(mal_id) DO UPDATE SET name=EXCLUDED.name,name_kanji=EXCLUDED.name_kanji,
                 image_url=EXCLUDED.image_url,mal_url=EXCLUDED.mal_url,raw_json=EXCLUDED.raw_json,updated_at=now()""",
                (c["mal_id"],c.get("name") or f"MAL {c['mal_id']}",c.get("name_kanji"),image_url,c.get("url"),json.dumps(c)))

    def upsert_role(self, person_id, character_id, anime_id, language, role, raw):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO voice_roles
                (person_mal_id,character_mal_id,anime_mal_id,language,role,raw_json)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(person_mal_id,character_mal_id,anime_mal_id,language)
                DO UPDATE SET role=EXCLUDED.role,raw_json=EXCLUDED.raw_json,updated_at=now()""",
                (person_id,character_id,anime_id,language or "",role,json.dumps(raw)))

    def link_season(self, anime_id, year, season):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO anime_seasons(anime_mal_id,year,season)
                VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""", (anime_id,year,season))

    def status(self):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id,job_name,started_at,finished_at,status,requests_made,
                           records_written,error FROM import_runs ORDER BY id""")
            return cur.fetchall()
