"""PREPARACIÓN DE LA FUENTE (no es la carga ETL).
Carga el CSV de Grammy en la tabla operacional grammy_source.public.grammy_awards y documenta la
conciliación de filas. Idempotente: TRUNCATE + COPY. El CSV original NO se modifica.

Uso:  python scripts/load_grammy_source.py          (local, usa .env / variables de entorno)
      docker compose exec airflow-scheduler python scripts/load_grammy_source.py
"""
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):      # consola de Windows (cp1252): imprimir tildes sin error
    sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import psycopg2

from src import config

COLS = ["year", "title", "published_at", "updated_at", "category", "nominee", "artist", "workers", "img", "winner"]


def main():
    raw = config.GRAMMY_CSV.read_bytes()
    df = pd.read_csv(io.BytesIO(raw))[COLS]
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    conn = psycopg2.connect(**config.pg_connect_kwargs(config.SOURCE_DB))
    with conn, conn.cursor() as cur:
        cur.execute((config.SQL_DIR / "source_setup.sql").read_text(encoding="utf-8"))
        cur.execute("TRUNCATE public.grammy_awards RESTART IDENTITY")
        cur.copy_expert(f"COPY public.grammy_awards({', '.join(COLS)}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
        cur.execute("""SELECT COUNT(*), COUNT(*) FILTER (WHERE artist IS NULL), COUNT(*) FILTER (WHERE nominee IS NULL),
                              COUNT(*) FILTER (WHERE winner), MIN(year), MAX(year) FROM public.grammy_awards""")
        n, art_null, nom_null, winners, ymin, ymax = cur.fetchone()
    conn.close()
    rec = {
        "loaded_at": datetime.now(timezone.utc).isoformat(), "csv": str(config.GRAMMY_CSV.name),
        "csv_sha256": hashlib.sha256(raw).hexdigest(), "table": f"{config.SOURCE_DB}.public.grammy_awards",
        "rows_csv": int(len(df)), "rows_table": n, "rows_reconcile": bool(len(df) == n),
        "null_artist": {"csv": int(df.artist.isna().sum()), "table": art_null},
        "null_nominee": {"csv": int(df.nominee.isna().sum()), "table": nom_null},
        "winner_true": {"csv": int(df.winner.sum()), "table": winners},
        "year_range": {"csv": [int(df.year.min()), int(df.year.max())], "table": [ymin, ymax]},
    }
    out = config.EVIDENCE / "source_preparation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    if not rec["rows_reconcile"]:
        sys.exit("ERROR: el conteo de filas del CSV y de la tabla NO coincide")


if __name__ == "__main__":
    main()
