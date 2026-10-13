"""Configuración central: rutas y conexiones. Todo se lee de variables de entorno
(ver .env.example) para que el mismo código corra en Docker (Airflow) y en local."""
import os
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
SPOTIFY_CSV = ROOT / "data" / "raw" / "spotify_dataset.csv"      # fuente 1 (archivo)
GRAMMY_CSV = ROOT / "data" / "raw" / "the_grammy_awards.csv"     # SOLO para preparar la fuente
STAGING = ROOT / "data" / "staging"                              # salidas intermedias por lote
EVIDENCE = ROOT / "docs" / "evidence"                            # evidencia de ejecuciones
SQL_DIR = ROOT / "sql"

WAREHOUSE = dict(
    host=os.getenv("WAREHOUSE_HOST", "localhost"),
    port=int(os.getenv("WAREHOUSE_PORT", "5433")),
    user=os.getenv("WAREHOUSE_USER", "etl_user"),
    password=os.getenv("WAREHOUSE_PASSWORD", "etl_password"),
)
SOURCE_DB = os.getenv("SOURCE_DB", "grammy_source")
DW_DB = os.getenv("DW_DB", "music_dw")


def db_url(dbname: str) -> str:
    w = WAREHOUSE
    return f"postgresql+psycopg2://{w['user']}:{w['password']}@{w['host']}:{w['port']}/{dbname}"


def pg_connect_kwargs(dbname: str) -> dict:
    w = WAREHOUSE
    return dict(host=w["host"], port=w["port"], user=w["user"], password=w["password"], dbname=dbname)


def batch_dir(batch_id: str) -> Path:
    d = STAGING / batch_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def evidence_dir(batch_id: str) -> Path:
    d = EVIDENCE / "runs" / batch_id
    d.mkdir(parents=True, exist_ok=True)
    return d
