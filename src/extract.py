"""EXTRACCIÓN. Regla: extraer SIN limpiar (no ocultar problemas de calidad de la fuente).
Cada función guarda el dato crudo en Parquet (staging) y devuelve SOLO metadatos
compactos (ruta, conteos). Así no usamos la base de metadatos de Airflow como
transporte de datos masivos."""
import json
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text

from . import config

log = logging.getLogger("airflow.task")

GRAMMY_COLUMNS = ["source_row_id", "year", "title", "published_at", "updated_at",
                  "category", "nominee", "artist", "workers", "img", "winner"]
GRAMMY_QUERY = f"SELECT {', '.join(GRAMMY_COLUMNS)} FROM public.grammy_awards ORDER BY source_row_id"


def _now():
    return datetime.now(timezone.utc).isoformat()


def extract_spotify(batch_id: str, fault: str = "none") -> dict:
    """Lee el CSV de Spotify (fuente de archivo) y lo deja en staging sin transformar."""
    log.info("[batch=%s] extract_spotify: leyendo %s", batch_id, config.SPOTIFY_CSV)
    df = pd.read_csv(config.SPOTIFY_CSV)
    if fault == "spotify_null_track_id":
        # PRUEBA B (controlada): simula un lote corrupto -> viola la regla CRITICAL DQ-S01
        idx = df.sample(frac=0.05, random_state=7).index
        df.loc[idx, "track_id"] = None
        log.warning("[batch=%s] FAULT INJECTION activa: %d track_id anulados", batch_id, len(idx))
    out = config.batch_dir(batch_id) / "spotify_raw.parquet"
    df.to_parquet(out, index=False)
    meta = {"source": "csv_file", "origin": str(config.SPOTIFY_CSV), "path": str(out),
            "rows": int(len(df)), "columns": list(df.columns), "fault": fault,
            "extracted_at": _now(), "batch_id": batch_id}
    (config.evidence_dir(batch_id) / "extract_spotify.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("[batch=%s] extract_spotify OK: %d filas -> %s", batch_id, len(df), out)
    return meta


def extract_grammys(batch_id: str, fault: str = "none", simulate_transient: str = "none",
                    try_number: int = 1) -> dict:
    """Extrae Grammy desde la BASE RELACIONAL (PostgreSQL), NO desde el CSV.
    La evidencia (host, base, tabla, query) queda en extract_grammys.json y en el log."""
    if simulate_transient == "extract_grammys" and try_number == 1:
        # Simula una caída transitoria de red/BD SOLO en el primer intento -> demuestra retry selectivo
        log.error("[batch=%s] extract_grammys: simulando interrupción transitoria de la BD", batch_id)
        raise ConnectionError("Simulated transient database outage (attempt 1)")
    engine = create_engine(config.db_url(config.SOURCE_DB))
    with engine.connect() as conn:
        db, host, usr = conn.execute(
            text("SELECT current_database(), COALESCE(inet_server_addr()::text,'local-socket'), current_user")).one()
        log.info("[batch=%s] extract_grammys: conectado a PostgreSQL db=%s host=%s user=%s", batch_id, db, host, usr)
        df = pd.read_sql(text(GRAMMY_QUERY), conn)
    engine.dispose()
    if fault == "grammy_invalid_year":
        idx = df.sample(frac=0.03, random_state=11).index
        df.loc[idx, "year"] = 1800            # año imposible -> viola DQ-G02 (CRITICAL)
        log.warning("[batch=%s] FAULT INJECTION activa: %d años inválidos", batch_id, len(idx))
    out = config.batch_dir(batch_id) / "grammys_raw.parquet"
    df.to_parquet(out, index=False)
    meta = {"source": "postgresql", "database": db, "server": str(host), "table": "public.grammy_awards",
            "query": GRAMMY_QUERY, "path": str(out), "rows": int(len(df)), "columns": list(df.columns),
            "fault": fault, "extracted_at": _now(), "batch_id": batch_id, "try_number": try_number}
    (config.evidence_dir(batch_id) / "extract_grammys.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("[batch=%s] extract_grammys OK: %d filas desde %s.%s -> %s", batch_id, len(df), db,
             "public.grammy_awards", out)
    return meta
