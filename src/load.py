"""CARGA al Data Warehouse dimensional (star schema).

ESTRATEGIA DE RERUN SEGURO: TRUNCATE-AND-LOAD ATÓMICO.
  Todo ocurre en UNA transacción: aplicar esquema -> TRUNCATE de dimensiones y hechos
  (RESTART IDENTITY CASCADE) -> recargar -> verificar conteos -> registrar en etl_batch_log -> COMMIT.
  * Rerun con el mismo lote  => resultado idéntico (mismos conteos y medidas), sin duplicados.
  * Falla a mitad de la carga => ROLLBACK: el DW conserva el estado completo anterior (nunca queda a medias).
  * Defensa adicional: UNIQUE(track_key, genre_key) y UNIQUE de llaves de negocio en las dimensiones.
La fuente es una foto completa (snapshot) del catálogo, por eso el reemplazo total es la estrategia adecuada.
"""
import io
import json
import logging
from datetime import datetime, timezone

import pandas as pd
import psycopg2

from . import config
from .rules import PREPARED_COLUMNS, RECOGNITION_LEVELS

log = logging.getLogger("airflow.task")

_STG_DDL = """
CREATE TEMP TABLE stg (
  track_id TEXT, track_genre TEXT, track_name TEXT, album_name TEXT, artists_raw TEXT,
  primary_artist TEXT, primary_artist_norm TEXT, n_artists SMALLINT, explicit BOOLEAN,
  popularity SMALLINT, duration_ms INTEGER, danceability REAL, energy REAL, valence REAL,
  acousticness REAL, instrumentalness REAL, liveness REAL, speechiness REAL, loudness REAL,
  tempo REAL, time_signature SMALLINT, grammy_artist_linked SMALLINT, grammy_track_linked SMALLINT,
  recognition_level TEXT, artist_grammy_nominations INTEGER, artist_grammy_wins INTEGER,
  artist_first_grammy_year INTEGER, artist_first_grammy_decade TEXT, track_grammy_nominations INTEGER
) ON COMMIT DROP"""

_TABLES = ["fact_track_listing", "dim_track", "dim_artist", "dim_genre", "dim_recognition"]


def _counts(cur) -> dict:
    out = {}
    for t in _TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        out[t] = cur.fetchone()[0]
    return out


def load_dw(prepared_path: str, batch_id: str, simulate_transient: str = "none", try_number: int = 1) -> dict:
    df = pd.read_parquet(prepared_path)[PREPARED_COLUMNS]
    log.info("[batch=%s] load_dw: %d filas preparadas -> %s", batch_id, len(df), config.DW_DB)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)

    conn = psycopg2.connect(**config.pg_connect_kwargs(config.DW_DB))
    try:
        with conn, conn.cursor() as cur:                       # `with conn` = COMMIT o ROLLBACK
            cur.execute((config.SQL_DIR / "dw_schema.sql").read_text(encoding="utf-8"))
            cur.execute("SELECT COUNT(*) FROM fact_track_listing")
            before = cur.fetchone()[0]
            cur.execute("TRUNCATE fact_track_listing, dim_track, dim_artist, dim_genre, dim_recognition "
                        "RESTART IDENTITY CASCADE")
            cur.execute(_STG_DDL)
            cur.copy_expert("COPY stg FROM STDIN WITH (FORMAT csv, NULL '')", buf)

            cur.executemany("INSERT INTO dim_recognition VALUES (%s,%s,%s)",
                            [(i + 1, lvl, i + 1) for i, lvl in enumerate(RECOGNITION_LEVELS)])
            cur.execute("INSERT INTO dim_genre(genre_name) SELECT DISTINCT track_genre FROM stg ORDER BY 1")
            cur.execute("""INSERT INTO dim_artist(artist_norm, artist_name, is_grammy_artist, grammy_nominations,
                                  grammy_wins, first_grammy_year, first_grammy_decade)
                           SELECT primary_artist_norm, MIN(primary_artist), BOOL_OR(grammy_artist_linked = 1),
                                  MAX(artist_grammy_nominations), MAX(artist_grammy_wins),
                                  MIN(artist_first_grammy_year), MIN(artist_first_grammy_decade)
                           FROM stg GROUP BY primary_artist_norm""")
            cur.execute("""INSERT INTO dim_track(track_id, track_name, album_name, artists_raw, n_artists,
                                  explicit, track_grammy_nominations)
                           SELECT DISTINCT ON (track_id) track_id, track_name, album_name, artists_raw, n_artists,
                                  explicit, track_grammy_nominations
                           FROM stg ORDER BY track_id, popularity DESC""")

            if simulate_transient == "load_dw" and try_number == 1:
                # Falla simulada A MITAD de carga (dimensiones ya insertadas, hecho aún no):
                # el ROLLBACK deja el DW intacto y el reintento carga limpio.
                raise ConnectionError("Simulated transient failure in the middle of load (attempt 1)")

            cur.execute("""INSERT INTO fact_track_listing(track_key, artist_key, genre_key, recognition_key, batch_id,
                                  popularity, duration_ms, danceability, energy, valence, acousticness,
                                  instrumentalness, liveness, speechiness, loudness, tempo)
                           SELECT t.track_key, a.artist_key, g.genre_key, r.recognition_key, %s,
                                  s.popularity, s.duration_ms, s.danceability, s.energy, s.valence, s.acousticness,
                                  s.instrumentalness, s.liveness, s.speechiness, s.loudness, s.tempo
                           FROM stg s
                           JOIN dim_track t       ON t.track_id = s.track_id
                           JOIN dim_artist a      ON a.artist_norm = s.primary_artist_norm
                           JOIN dim_genre g       ON g.genre_name = s.track_genre
                           JOIN dim_recognition r ON r.recognition_level = s.recognition_level""", (batch_id,))
            counts = _counts(cur)
            if counts["fact_track_listing"] != len(df):
                raise RuntimeError(f"Conciliación de carga falló: fact={counts['fact_track_listing']} vs "
                                   f"preparado={len(df)} (se hace ROLLBACK)")
            cur.execute("""INSERT INTO etl_batch_log(batch_id, status, rows_dim_track, rows_dim_artist,
                                  rows_dim_genre, rows_fact) VALUES (%s,'SUCCESS',%s,%s,%s,%s)""",
                        (batch_id, counts["dim_track"], counts["dim_artist"], counts["dim_genre"],
                         counts["fact_track_listing"]))
            cur.execute("""SELECT COUNT(*), ROUND(SUM(popularity)::numeric,0), ROUND(AVG(popularity)::numeric,4)
                           FROM fact_track_listing""")
            n, sum_pop, avg_pop = cur.fetchone()
            cur.execute((config.SQL_DIR / "kpi_queries.sql").read_text(encoding="utf-8"))    # vistas de KPIs
    finally:
        conn.close()

    summary = {"batch_id": batch_id, "loaded_at": datetime.now(timezone.utc).isoformat(), "strategy":
               "atomic truncate-and-load (single transaction)", "fact_rows_before_load": before,
               "rows_loaded": counts, "measure_checks": {"fact_rows": n, "sum_popularity": float(sum_pop),
                                                         "avg_popularity": float(avg_pop)},
               "try_number": try_number}
    (config.evidence_dir(batch_id) / "load_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("[batch=%s] load_dw OK (COMMIT): %s | sum_popularity=%s avg=%s", batch_id, counts, sum_pop, avg_pop)
    return summary
