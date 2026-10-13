"""Foto del estado del DW para demostrar RERUN SEGURO (requisito 7.3).
Uso:  python scripts/dw_snapshot.py antes     (antes del rerun)
      python scripts/dw_snapshot.py despues   (después del rerun)
      python scripts/dw_snapshot.py compare antes despues
Guarda docs/evidence/dw_snapshot_<etiqueta>.json con conteos, medidas y un checksum del contenido."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):      # consola de Windows (cp1252): imprimir tildes sin error
    sys.stdout.reconfigure(encoding="utf-8")
import psycopg2

from src import config

TABLES = ["dim_recognition", "dim_genre", "dim_artist", "dim_track", "fact_track_listing"]


def snapshot() -> dict:
    conn = psycopg2.connect(**config.pg_connect_kwargs(config.DW_DB))
    cur = conn.cursor()
    snap = {"taken_at": datetime.now(timezone.utc).isoformat(), "row_counts": {}}
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        snap["row_counts"][t] = cur.fetchone()[0]
    cur.execute("SELECT SUM(popularity), ROUND(AVG(popularity)::numeric,4), SUM(duration_ms) FROM fact_track_listing")
    s, a, d = cur.fetchone()
    snap["measures"] = {"sum_popularity": float(s), "avg_popularity": float(a), "sum_duration_ms": float(d)}
    # checksum del CONTENIDO (independiente de las llaves surrogate)
    cur.execute("""SELECT md5(string_agg(t.track_id || '|' || g.genre_name || '|' || f.popularity || '|' ||
                                         r.recognition_level, ',' ORDER BY t.track_id, g.genre_name))
                   FROM fact_track_listing f JOIN dim_track t USING(track_key) JOIN dim_genre g USING(genre_key)
                   JOIN dim_recognition r USING(recognition_key)""")
    snap["content_md5"] = cur.fetchone()[0]
    cur.execute("SELECT recognition_level, avg_popularity FROM vw_kpi_popularity_by_recognition")
    snap["kpi1_avg_popularity"] = {k: float(v) for k, v in cur.fetchall()}
    cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE status='SUCCESS') FROM etl_batch_log")
    snap["etl_batch_log"] = dict(zip(["entries", "success"], cur.fetchone()))
    conn.close()
    return snap


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "compare":
        a, b = (json.loads((config.EVIDENCE / f"dw_snapshot_{x}.json").read_text(encoding="utf-8")) for x in sys.argv[2:4])
        same = all(a[k] == b[k] for k in ("row_counts", "measures", "content_md5", "kpi1_avg_popularity"))
        print(json.dumps({k: {"antes": a[k], "despues": b[k]} for k in
                          ("row_counts", "measures", "content_md5")}, indent=2))
        print("\nRESULTADO:", "IDÉNTICO -> sin efectos duplicados" if same else "DIFERENTE -> revisar!")
        sys.exit(0 if same else 1)
    label = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    snap = snapshot()
    out = config.EVIDENCE / f"dw_snapshot_{label}.json"
    out.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    print(json.dumps(snap, indent=2))
    print("->", out)


if __name__ == "__main__":
    main()
