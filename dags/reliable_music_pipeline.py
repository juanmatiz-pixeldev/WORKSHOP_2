"""
reliable_music_pipeline  ·  Workshop-2 (Airflow 3.1.8, TaskFlow API)

Topología (dos ramas independientes que convergen):

  extract_spotify -> validate_spotify_raw --\
                                             >-- transform_and_integrate -> validate_prepared -> load_dw
  extract_grammys -> validate_grammys_raw --/

* El DAG SOLO orquesta (dependencias, reintentos, política de fallos). La lógica vive en src/*.py.
* Las tareas intercambian rutas y metadatos compactos (dict pequeño por XCom), NUNCA DataFrames:
  los datos masivos viajan por archivos Parquet en data/staging/<batch_id>/.
* Fallas deterministas de calidad (regla CRITICAL) -> AirflowFailException: la tarea falla SIN reintento
  y las tareas posteriores quedan en 'upstream_failed' (no corren).
* Reintentos solo donde hay fallas transitorias posibles (extraer de BD, cargar a BD). Ver docs/failure_policy.md.

Parámetros al disparar (Trigger DAG w/ config):
  batch_id           : identificador del lote (misma carpeta de staging y mismo batch en el DW).
  fault_injection    : none | spotify_null_track_id | grammy_invalid_year   (PRUEBA B: falla CRITICAL controlada)
  simulate_transient : none | extract_grammys | load_dw   (falla transitoria en el 1.er intento -> demuestra retry)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow.exceptions import AirflowFailException
from airflow.sdk import Param, dag, get_current_context, task

log = logging.getLogger("airflow.task")

# Política de reintentos (justificada en docs/failure_policy.md)
RETRY_FILE_READ = dict(retries=1, retry_delay=timedelta(seconds=10))                       # CSV local
RETRY_DB_EXTRACT = dict(retries=3, retry_delay=timedelta(seconds=20), retry_exponential_backoff=True,
                        max_retry_delay=timedelta(minutes=2))                              # BD fuente
RETRY_DB_LOAD = dict(retries=2, retry_delay=timedelta(seconds=30))                         # carga atómica = idempotente
NO_RETRY = dict(retries=0)                                                                 # determinista


def _ctx():
    c = get_current_context()
    return c["params"], c["ti"].try_number


@dag(
    dag_id="reliable_music_pipeline",
    description="Spotify (CSV) + Grammy (PostgreSQL) -> validación GX -> transformación -> DW estrella",
    schedule=None,                       # ejecución batch bajo demanda (manual / API)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,                   # evita dos cargas simultáneas sobre el mismo DW
    params={
        "batch_id": Param("batch_001", type="string", description="Identificador del lote"),
        "fault_injection": Param("none", type="string",
                                 enum=["none", "spotify_null_track_id", "grammy_invalid_year"],
                                 description="PRUEBA B: activa un lote corrupto (viola una regla Critical)"),
        "simulate_transient": Param("none", type="string", enum=["none", "extract_grammys", "load_dw"],
                                    description="Falla transitoria en el 1.er intento (demuestra retry selectivo)"),
    },
    default_args={"owner": "data-engineering"},
    tags=["workshop-2", "etl", "great-expectations"],
    doc_md=__doc__,
)
def reliable_music_pipeline():

    # ------------------------------ Rama Spotify ------------------------------
    @task(**RETRY_FILE_READ)
    def extract_spotify() -> dict:
        from src import extract
        p, _ = _ctx()
        return extract.extract_spotify(p["batch_id"], p["fault_injection"])

    @task(**NO_RETRY)
    def validate_spotify_raw(meta: dict) -> dict:
        import pandas as pd
        from src import validation
        from src.errors import DataQualityError
        try:
            res = validation.run_gate("spotify_raw", pd.read_parquet(meta["path"]), meta["batch_id"])
        except DataQualityError as e:
            raise AirflowFailException(str(e))      # falla determinista: sin retry, downstream bloqueado
        return {**meta, "validation": res["policy_outcome"], "warnings": res["failed_warning"]}

    # ------------------------------ Rama Grammy ------------------------------
    @task(**RETRY_DB_EXTRACT)
    def extract_grammys() -> dict:
        from src import extract
        p, attempt = _ctx()
        return extract.extract_grammys(p["batch_id"], p["fault_injection"], p["simulate_transient"], attempt)

    @task(**NO_RETRY)
    def validate_grammys_raw(meta: dict) -> dict:
        import pandas as pd
        from src import validation
        from src.errors import DataQualityError
        try:
            res = validation.run_gate("grammys_raw", pd.read_parquet(meta["path"]), meta["batch_id"])
        except DataQualityError as e:
            raise AirflowFailException(str(e))
        return {**meta, "validation": res["policy_outcome"], "warnings": res["failed_warning"]}

    # ------------------------------ Convergencia ------------------------------
    @task(**NO_RETRY)
    def transform_and_integrate(spotify: dict, grammys: dict) -> dict:
        from src import transform
        return transform.transform_and_integrate(spotify, grammys, spotify["batch_id"])

    @task(**NO_RETRY)
    def validate_prepared(prep: dict) -> dict:
        import pandas as pd
        from src import validation
        from src.errors import DataQualityError
        try:
            res = validation.run_gate("prepared", pd.read_parquet(prep["prepared_path"]), prep["batch_id"],
                                      ctx={"expected_rows": prep["expected_rows"]})
        except DataQualityError as e:
            raise AirflowFailException(str(e))
        return {**prep, "validation": res["policy_outcome"]}

    @task(**RETRY_DB_LOAD)
    def load_dw(prep: dict) -> dict:
        from src import load
        p, attempt = _ctx()
        return load.load_dw(prep["prepared_path"], prep["batch_id"], p["simulate_transient"], attempt)

    # ------------------------------ Dependencias ------------------------------
    spotify_ok = validate_spotify_raw(extract_spotify())
    grammys_ok = validate_grammys_raw(extract_grammys())
    prepared = transform_and_integrate(spotify_ok, grammys_ok)    # espera a AMBAS ramas (all_success)
    load_dw(validate_prepared(prepared))                          # load solo si validate_prepared tuvo éxito


reliable_music_pipeline()
