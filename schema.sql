CREATE TABLE IF NOT EXISTS people (
    mal_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    given_name TEXT,
    family_name TEXT,
    alternate_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    birthday TIMESTAMPTZ,
    website_url TEXT,
    mal_url TEXT,
    image_url TEXT,
    favorites INTEGER,
    about TEXT,
    raw_json JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anime (
    mal_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    title_english TEXT,
    title_japanese TEXT,
    type TEXT,
    source TEXT,
    episodes INTEGER,
    status TEXT,
    aired_from TIMESTAMPTZ,
    aired_to TIMESTAMPTZ,
    season TEXT,
    year INTEGER,
    image_url TEXT,
    mal_url TEXT,
    raw_json JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS characters (
    mal_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_kanji TEXT,
    image_url TEXT,
    mal_url TEXT,
    raw_json JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voice_roles (
    person_mal_id INTEGER NOT NULL REFERENCES people(mal_id) ON DELETE CASCADE,
    character_mal_id INTEGER NOT NULL REFERENCES characters(mal_id) ON DELETE CASCADE,
    anime_mal_id INTEGER NOT NULL REFERENCES anime(mal_id) ON DELETE CASCADE,
    language TEXT NOT NULL DEFAULT '',
    role TEXT,
    source TEXT NOT NULL DEFAULT 'tenrai',
    raw_json JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (person_mal_id, character_mal_id, anime_mal_id, language)
);

CREATE TABLE IF NOT EXISTS anime_seasons (
    anime_mal_id INTEGER NOT NULL REFERENCES anime(mal_id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    season TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (anime_mal_id, year, season)
);

CREATE TABLE IF NOT EXISTS import_state (
    job_name TEXT PRIMARY KEY,
    state JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS import_runs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    requests_made INTEGER NOT NULL DEFAULT 0,
    records_written INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_voice_roles_person ON voice_roles(person_mal_id);
CREATE INDEX IF NOT EXISTS idx_voice_roles_character ON voice_roles(character_mal_id);
CREATE INDEX IF NOT EXISTS idx_voice_roles_anime ON voice_roles(anime_mal_id);
CREATE INDEX IF NOT EXISTS idx_anime_seasons_year_season ON anime_seasons(year, season);
CREATE INDEX IF NOT EXISTS idx_people_favorites ON people(favorites DESC);
