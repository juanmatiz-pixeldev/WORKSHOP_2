# Registro de evidencia de confiabilidad (§4.4 / §8.3)

`reference_run/` contiene las salidas de una **ejecución de verificación** del pipeline (Airflow 3.1.8 + PostgreSQL 16 + GX 1.24)
para que veas el formato esperado. **Regenera tu propia evidencia** corriendo el pipeline en tu Docker y guarda tus capturas
(legibles, recortadas y con interpretación) en esta carpeta. Los JSON de cada ejecución se escriben solos en `docs/evidence/runs/<batch_id>/`.

| Evidence ID | Run / Task | Artefacto o ruta | Qué demuestra | Regla / Política |
|---|---|---|---|---|
| EV-01 | Preparación de la fuente | `source_preparation.json` | CSV Grammy (4,810 filas) = tabla `grammy_source.public.grammy_awards` (conciliación + sha256 del CSV) | §6.2 |
| EV-02 | `extract_grammys` (Test A) | `runs/<batch>/extract_grammys.json` + log | La extracción de Grammy lee de **PostgreSQL** (db, servidor, tabla, query), no del CSV | §4.3 |
| EV-03 | `validate_spotify_raw` / `validate_grammys_raw` (Test A) | `runs/<batch>/validation_*_raw.json` | Gates raw exitosos; Grammy `PASS_WITH_WARNINGS` por DQ-G07 | DQ-S*, DQ-G* |
| EV-04 | `transform_and_integrate` (Test A) | `runs/<batch>/reconciliation.json` | 114,000→113,549 filas; match 47.87%; joins preservan filas | T-01…T-08 |
| EV-05 | `validate_prepared` (Test A) | `runs/<batch>/validation_prepared.json` | Gate 2 exitoso: suite distinta, 11 reglas | DQ-P01…P11 |
| EV-06 | `load_dw` (Test A) | `runs/<batch>/load_summary.json` | Conteos cargados por tabla y medidas | §6.10 |
| EV-07 | Test A (UI) | **Captura**: Airflow Grid/Graph con las 7 tareas en `success` | Ejecución exitosa end-to-end | Test A |
| EV-08 | Test B `validate_spotify_raw` | `reference_run/test_b_…/validation_spotify_raw.json` + log | Falla **Critical DQ-S01** (5% de `track_id` nulos) bloquea el gate | DQ-S01 |
| EV-09 | Test B (UI) | **Captura**: Graph con `validate_spotify_raw` en *failed* y `transform/validate_prepared/load_dw` en *upstream_failed* + log de la tarea | Downstream no procede; falla visible y diagnosticable | Test B |
| EV-10 | Retry selectivo `extract_grammys` | `reference_run/safe_rerun/log_excerpt_transient_failure_extract.txt` + **captura** de *Task Instance → Tries* | Falla transitoria en intento 1 → `up_for_retry` → éxito en intento 2 | Política de retry |
| EV-11 | Retry/rollback en `load_dw` | `reference_run/safe_rerun/log_excerpt_transient_failure_mid_load.txt` | Falla a mitad de carga → ROLLBACK → reintento limpio; DW intacto | Carga atómica |
| EV-12 | Rerun seguro | `reference_run/safe_rerun/dw_snapshot_antes.json` / `…despues.json` + salida de `dw_snapshot.py compare` | Mismos conteos, medidas y checksum tras rerun del mismo lote | §7.3 |
| EV-13 | Dashboard | **Captura** del BI conectado a `music_dw` + `reference_run/dashboard/*.png` | KPIs salen del DW (no de CSV) | §8.1 |
| EV-14 | Versión de Airflow | **Captura**/salida de `airflow version` = 3.1.8 | Requisito de versión | §6.2 |
