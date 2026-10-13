-- ============================================================================
-- sql/dw_schema.sql  ·  ESQUEMA EN ESTRELLA del Data Warehouse (base music_dw)
-- Idempotente (CREATE ... IF NOT EXISTS): load_dw lo aplica en cada ejecución.
--
-- Proceso de negocio : Presencia de pistas de Spotify por género y su vínculo
--                      con el reconocimiento de los Premios Grammy.
-- Grano de la tabla de hechos:
--      UNA fila = UNA pista de Spotify (track_id) en UN género (track_genre).
-- Estrategia de llaves:
--      Surrogate keys enteras en cada dimensión + business key con UNIQUE
--      (track_id, artist_norm, genre_name, recognition_level).
-- ============================================================================

-- ---------- Dimensiones ----------
CREATE TABLE IF NOT EXISTS dim_recognition (
    recognition_key   SMALLINT PRIMARY KEY,
    recognition_level TEXT NOT NULL UNIQUE,
    sort_order        SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_genre (
    genre_key   SERIAL PRIMARY KEY,
    genre_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_artist (
    artist_key           SERIAL PRIMARY KEY,
    artist_norm          TEXT NOT NULL UNIQUE,      -- business key (nombre normalizado)
    artist_name          TEXT NOT NULL,             -- nombre para mostrar
    is_grammy_artist     BOOLEAN NOT NULL,
    grammy_nominations   INTEGER NOT NULL DEFAULT 0,
    grammy_wins          INTEGER NOT NULL DEFAULT 0,
    first_grammy_year    INTEGER,
    first_grammy_decade  TEXT                       -- p.ej. '1990s'; NULL si no Grammy
);

CREATE TABLE IF NOT EXISTS dim_track (
    track_key                SERIAL PRIMARY KEY,
    track_id                 CHAR(22) NOT NULL UNIQUE,  -- business key (Spotify)
    track_name               TEXT NOT NULL,
    album_name               TEXT,
    artists_raw              TEXT NOT NULL,
    n_artists                SMALLINT NOT NULL,
    explicit                 BOOLEAN NOT NULL,
    track_grammy_nominations INTEGER NOT NULL DEFAULT 0
);

-- ---------- Hechos ----------
CREATE TABLE IF NOT EXISTS fact_track_listing (
    track_listing_key BIGSERIAL PRIMARY KEY,
    track_key         INTEGER  NOT NULL REFERENCES dim_track(track_key),
    artist_key        INTEGER  NOT NULL REFERENCES dim_artist(artist_key),
    genre_key         INTEGER  NOT NULL REFERENCES dim_genre(genre_key),
    recognition_key   SMALLINT NOT NULL REFERENCES dim_recognition(recognition_key),
    batch_id          TEXT     NOT NULL,
    -- Medidas (consistentes con el grano)
    popularity        SMALLINT NOT NULL CHECK (popularity BETWEEN 0 AND 100),
    duration_ms       INTEGER  CHECK (duration_ms IS NULL OR duration_ms > 0),
    danceability      REAL, energy REAL, valence REAL, acousticness REAL,
    instrumentalness  REAL, liveness REAL, speechiness REAL,
    loudness          REAL,
    tempo             REAL CHECK (tempo IS NULL OR tempo > 0),
    -- Garantía de idempotencia / no duplicados: una pista por género
    CONSTRAINT uq_fact_track_genre UNIQUE (track_key, genre_key)
);
CREATE INDEX IF NOT EXISTS ix_fact_artist      ON fact_track_listing(artist_key);
CREATE INDEX IF NOT EXISTS ix_fact_genre       ON fact_track_listing(genre_key);
CREATE INDEX IF NOT EXISTS ix_fact_recognition ON fact_track_listing(recognition_key);

-- ---------- Bitácora de cargas (NO se trunca: historial de ejecuciones) ----------
CREATE TABLE IF NOT EXISTS etl_batch_log (
    load_id        SERIAL PRIMARY KEY,
    batch_id       TEXT NOT NULL,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status         TEXT NOT NULL,
    rows_dim_track INTEGER, rows_dim_artist INTEGER, rows_dim_genre INTEGER,
    rows_fact      INTEGER
);
