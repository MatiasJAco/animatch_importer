# Tenrai -> PostgreSQL importer

A conservative Linux importer for the Tenrai API with a deliberate two-phase design:

```text
Tenrai API --rate limited--> local raw JSON files --no network--> PostgreSQL
```

PostgreSQL is **not required for the download phase**. This is intentional. The raw API
responses are the durable dataset and can be re-imported after changing the database schema,
recovering from a PostgreSQL failure, or restarting the importer.

## What it collects

- Top 100 most-favorited people (configurable)
- Full person records
- All paginated voice roles for those people
- Seasonal anime for a selected year
- Characters and voice actors for each seasonal anime
- Actor and character image URLs
- Raw API JSON for reproducibility

The database uses MAL IDs as external identifiers.

## Tenrai limits

Current Tenrai documentation lists 120 RPM / 4 RPS for public requests and 300 RPM / 5 RPS
for Server Keys. The downloader defaults to 2 RPS / 90 RPM and one request at a time. It honors
`Retry-After` on HTTP 429 and backs off on transient errors and temporary HTTP 403 blocks.

See: https://api.tenrai.org/documentation

## Installation

```bash
sudo dnf install -y python3.11
sudo mkdir -p /opt/tenrai-importer /data01/tenrai-data
sudo chown -R "$USER:$USER" /opt/tenrai-importer /data01/tenrai-data

python3.11 -m venv /opt/tenrai-importer/venv
source /opt/tenrai-importer/venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
chmod 600 .env
```

Set `TENRAI_DATA_DIR` to a persistent filesystem. If PostgreSQL is local, `DATABASE_URL` can
point at `127.0.0.1`.

## Phase 1: download from Tenrai

No PostgreSQL connection is opened by these commands.

```bash
python -m tenrai_importer.cli fetch-top-people --people-limit 100
python -m tenrai_importer.cli fetch-season --year 2026 --season winter
python -m tenrai_importer.cli fetch-season --year 2026 --season spring
python -m tenrai_importer.cli fetch-year --year 2026
```

Existing raw files are reused. Use `--refresh` only when you deliberately want to download
those endpoints again.

Files are written atomically, for example:

```text
/data01/tenrai-data/
├── top_people/pages/page-0001-limit-50.json
├── people/1/full.json
├── people/1/voices/page-0001.json
└── seasons/2026/
    ├── winter/pages/page-0001.json
    └── winter/anime/12345/characters.json
```

If the process is interrupted, completed files remain valid and the next run continues using
them instead of re-downloading them.

## Phase 2: import local files into PostgreSQL

Initialize PostgreSQL separately, then:

```bash
python -m tenrai_importer.cli init-db
python -m tenrai_importer.cli import-top-people --limit 100
python -m tenrai_importer.cli import-season --year 2026 --season winter
python -m tenrai_importer.cli import-season --year 2026 --season spring
python -m tenrai_importer.cli import-year --year 2026
```

These commands make **zero Tenrai API requests**.

Each anime import is transactional. If one anime fails, its transaction is rolled back and the
original exception is preserved. The importer then marks the `import_runs` row as `failed`; it
does not attempt SQL statements against an aborted PostgreSQL transaction.

## One-command sync

For systemd or a simple scheduled job:

```bash
python -m tenrai_importer.cli sync --year 2026 --people-limit 100
```

`sync` first completes/reuses the local raw dataset, then imports that local dataset. A database
failure therefore does not cause the next run to re-download already-complete API responses.

## PostgreSQL

The importer expects PostgreSQL to already exist for database commands. It does not install,
initialize, or manage PostgreSQL itself.

Example:

```sql
CREATE USER tenrai_importer WITH PASSWORD 'CHANGE_THIS';
CREATE DATABASE anime_db OWNER tenrai_importer;
```

Then set:

```text
DATABASE_URL=postgresql://tenrai_importer:CHANGE_THIS@127.0.0.1:5432/anime_db
```

## Existing broken `running` jobs

The previous importer version could leave `import_runs.status = 'running'` after a database
error. Those are historical records. Do not delete the actual anime data just because a run is
marked running.

After installing this version, inspect them with:

```bash
python -m tenrai_importer.cli status
```

You can mark the known stale rows from the old importer explicitly if desired:

```sql
UPDATE import_runs
SET status = 'failed', finished_at = COALESCE(finished_at, now()),
    error = COALESCE(error, 'Interrupted/aborted by previous importer version')
WHERE status = 'running';
```

Review the rows before running that SQL if another importer is currently active.

## systemd

The included unit runs the two phases through `sync`:

```bash
sudo useradd --system --home /opt/tenrai-importer --shell /sbin/nologin tenrai
sudo install -d -o tenrai -g tenrai /opt/tenrai-importer /data01/tenrai-data
sudo install -m 0644 systemd/tenrai-sync.service /etc/systemd/system/
sudo install -m 0644 systemd/tenrai-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tenrai-sync.timer
```

Adjust the service `--year` as appropriate.

## Design notes

- No API parallelism.
- Conservative rate limiting.
- `Retry-After` is honored.
- HTTP 5xx/network failures use bounded exponential backoff.
- HTTP 403 is treated as a temporary block and is not hammered.
- Raw responses are kept locally.
- PostgreSQL writes use UPSERTs.
- PostgreSQL writes are transactional per anime/person unit.
- Images are represented by source URLs; image binaries are not downloaded.
- The local raw dataset is the recovery/checkpoint mechanism for network acquisition.
