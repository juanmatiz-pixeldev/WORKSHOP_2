# Política de fallos, reintentos y observabilidad (Sección 6.11)

## Política de fallos

| Condición | Severidad / Tipo | Respuesta del pipeline | ¿Retry? | Justificación |
|---|---|---|---|---|
| Regla **Critical** de GX falla en gate raw (p. ej. DQ-S01, DQ-G02) | Determinista (datos) | La tarea `validate_*_raw` termina en **failed** (`AirflowFailException`); `transform`, `validate_prepared` y `load_dw` quedan `upstream_failed`. Evidencia JSON + log con Rule ID | **No** | Repetir con el mismo lote reproduce el mismo fallo; se requiere corregir el dato/fuente |
| Regla **Critical** falla en `validate_prepared` (DQ-P01…P09) | Determinista (transformación/contrato) | `load_dw` **no se ejecuta**; el DW conserva su estado previo | **No** | Evita cargar datos que violarían el modelo dimensional |
| Regla **Warning** falla (p. ej. DQ-G07, DQ-S06) | Calidad tolerable | Se registra (WARNING en log + JSON, `PASS_WITH_WARNINGS`) y el pipeline **continúa** | No aplica | El lote sigue siendo utilizable; las transformaciones T-02/T-03 tratan el problema; visibilidad garantizada |
| Regla **Informational** falla | Tendencia | Solo se registra | No aplica | Señal de monitoreo; no bloquea |
| BD fuente Grammy no disponible / corte de red en `extract_grammys` | Transitoria operacional | Reintento con backoff | **Sí: 3 × 20 s, backoff exponencial (máx. 2 min)** | Una caída corta de BD suele resolverse en segundos; el extract es de solo lectura (seguro de repetir) |
| CSV Spotify temporalmente no legible (volumen aún montando) | Transitoria operacional | Reintento | **Sí: 1 × 10 s** | Fallo raro; un único reintento basta; leer es idempotente |
| Falla de conexión/escritura durante `load_dw` | Transitoria operacional | **ROLLBACK** de la transacción y reintento | **Sí: 2 × 30 s** | La carga es atómica (truncate-and-load en 1 transacción) → repetirla es seguro e idempotente |
| Columna faltante / esquema inválido (DQ-S02, DQ-G01, DQ-P01) | Determinista (contrato) | Falla inmediata del gate, sin retry | **No** | Un reintento no crea la columna |
| `transform_and_integrate` lanza error (p. ej. join multiplica filas → `IntegrationError`) | Determinista (código/datos) | Falla de la tarea, sin load | **No** | Es un bug o un cambio de datos, no una condición transitoria |

> **No hay `retries=3` global.** Cada tarea declara su política (`RETRY_FILE_READ`, `RETRY_DB_EXTRACT`, `RETRY_DB_LOAD`,
> `NO_RETRY` en `dags/reliable_music_pipeline.py`). `max_active_runs=1` evita dos cargas simultáneas.

## Qué ocurre tras una ejecución parcial o fallida
* **Falla en un gate o en transform:** no se escribe nada en el DW. El staging del lote (`data/staging/<batch>/`) y la evidencia
  (`docs/evidence/runs/<batch>/`) se conservan para investigar.
* **Falla durante `load_dw`:** la transacción hace ROLLBACK; el DW queda exactamente como estaba (el hecho **no** queda a medias).
  `etl_batch_log` solo registra cargas exitosas.
* **Rerun del mismo lote:** TRUNCATE + recarga dentro de la misma transacción → mismo estado final (verificado con
  `scripts/dw_snapshot.py compare`).

## Observabilidad: cómo responder cada pregunta
| Pregunta | Dónde verlo |
|---|---|
| ¿Qué corrió? | Airflow UI → DAG `reliable_music_pipeline` → Run (`run_id`) → Grid; los logs llevan `[batch=<id>]` |
| ¿Cuándo? | Grid/Task Instance: *Start date*, *End date*, *Duration*; logical date del run |
| ¿Tuvo éxito? | Estado del DagRun y de cada Task Instance (success/failed/upstream_failed/up_for_retry) + `docs/evidence/runs/<batch>/load_summary.json` |
| ¿Dónde falló? | Tarea en rojo (`failed`) y tareas naranja (`upstream_failed`) en el Graph/Grid |
| ¿Por qué? | Log de la tarea: mensaje `BLOQUEADO por regla(s) CRITICAL: DQ-… (umbral)` + `validation_<capa>.json` (observed_value, unexpected_count) |
| ¿Qué pasó después? | Log de reintentos (`up_for_retry`, `try_number=2`), warnings que continúan, o parada |
