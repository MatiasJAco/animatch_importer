import argparse
import sys
from .client import TenraiClient
from .config import load_config
from .db import Database
from .fetcher import Fetcher, SEASONS
from .importer import Importer
from .storage import RawStore
from .sync import Sync

def parser():
    p = argparse.ArgumentParser(description="Tenrai raw downloader and PostgreSQL importer")
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("init-db")
    s.add_parser("status")

    x = s.add_parser("fetch-top-people")
    x.add_argument("--people-limit", type=int, default=100)
    x.add_argument("--refresh", action="store_true")

    x = s.add_parser("fetch-season")
    x.add_argument("--year", type=int, required=True)
    x.add_argument("--season", choices=SEASONS, required=True)
    x.add_argument("--refresh", action="store_true")

    x = s.add_parser("fetch-year")
    x.add_argument("--year", type=int, required=True)
    x.add_argument("--refresh", action="store_true")

    x = s.add_parser("import-top-people")
    x.add_argument("--limit", type=int, default=100)

    x = s.add_parser("import-season")
    x.add_argument("--year", type=int, required=True)
    x.add_argument("--season", choices=SEASONS, required=True)

    x = s.add_parser("import-year")
    x.add_argument("--year", type=int, required=True)
    x.add_argument("--seasons", default=','.join(SEASONS))

    x = s.add_parser("sync")
    x.add_argument("--year", type=int, required=True)
    x.add_argument("--people-limit", type=int, default=100)
    x.add_argument("--refresh", action="store_true")
    return p

def main():
    args = parser().parse_args()
    needs_db = args.command in {"init-db", "status", "import-top-people", "import-season", "import-year", "sync"}
    cfg = load_config(require_database=needs_db)
    store = RawStore(cfg.data_dir)
    try:
        if args.command == "init-db":
            db = Database(cfg.database_url)
            try:
                db.init_schema()
            finally:
                db.close()
            print("Database schema initialized.")
            return 0

        if args.command == "status":
            db = Database(cfg.database_url)
            try:
                for row in db.status():
                    print(row)
            finally:
                db.close()
            return 0

        client = TenraiClient(cfg) if args.command.startswith("fetch-") or args.command == "sync" else None

        if args.command.startswith("fetch-"):
            fetcher = Fetcher(client, store)
            if args.command == "fetch-top-people":
                count = fetcher.top_people_voices(args.people_limit, args.refresh)
            elif args.command == "fetch-season":
                count = fetcher.season(args.year, args.season, args.refresh)
            else:
                count = fetcher.seasons(args.year, SEASONS, args.refresh)
            print(f"Raw data ready under: {cfg.data_dir}")
            print(f"Entries processed: {count}")
            print(f"Tenrai API requests made: {client.request_count}")
            return 0

        db = Database(cfg.database_url)
        try:
            importer = Importer(db, store)
            if args.command == "import-top-people":
                count = importer.import_top_people(args.limit)
            elif args.command == "import-season":
                count = importer.import_season(args.year, args.season)
            elif args.command == "import-year":
                seasons = [x.strip().lower() for x in args.seasons.split(',') if x.strip()]
                count = importer.import_year(args.year, seasons)
            else:
                sync = Sync(Fetcher(client, store), importer)
                count = sync.run(args.year, args.people_limit, args.refresh)
            print(f"Database records processed: {count}")
            if client:
                print(f"Tenrai API requests made: {client.request_count}")
            return 0
        finally:
            db.close()
    except KeyboardInterrupt:
        print("Interrupted. Completed raw files are retained; re-run safely.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
