# Workshop-2 · Pipeline batch confiable: Spotify (CSV) + Grammy (PostgreSQL) → Data Warehouse

> *Un Data Engineer no construye scripts: diseña sistemas.*  
> Curso ETL (G01) · UAO · Airflow **3.1.8** (TaskFlow API) · Great Expectations **1.24** · PostgreSQL 16 · Docker Compose

## 1. Problema y objetivo analítico
Integrar dos fuentes heterogéneas —**Spotify** (archivo CSV, 114,000 filas pista×género) y **Grammy Awards** (tabla relacional, 4,810 nominaciones)—
en un **Data Warehouse dimensional confiable** que permita estudiar cómo se relaciona el reconocimiento Grammy con la popularidad y características de las pistas.
El pipeline *no asume que los datos son correctos: los verifica* (dos compuertas de validación) y falla de forma **controlada y observable**.

## 2. Requisitos analíticos
| ID | Pregunta | KPI |
|---|---|---|
| AR-1 | ¿Las pistas con vínculo Grammy son más populares? | Popularidad promedio por nivel de reconocimiento |
| AR-2 | ¿Qué géneros concentran más pistas con vínculo Grammy? | % vinculado por género |
| AR-3 | ¿Cambia la popularidad según la década del primer Grammy del artista? | Popularidad por década |

Detalle y alcance: [`docs/analytical_requirements.md`](docs/analytical_requirements.md).

## 3. Fuentes de datos
| Fuente | Forma entregada | Extracción del pipeline |
|---|---|---|
| Spotify | `data/raw/spotify_dataset.csv` | Lee el archivo CSV |
| Grammy | `data/raw/the_grammy_awards.csv` | **Desde PostgreSQL** (`grammy_source.public.grammy_awards`). El CSV solo sirve para *preparar* la fuente (`scripts/load_grammy_source.py`), no se lee en el DAG. |

## 4. Mapa del repositorio: qué hace cada cosa
```
workshop-2/
├── docker-compose.yaml      Levanta TODO: Airflow 3.1.8 (api-server, scheduler, dag-processor), Postgres de metadatos,
│                            Postgres de datos (grammy_source + music_dw) y Metabase opcional.
├── Dockerfile               Imagen apache/airflow:3.1.8 + dependencias del proyecto (con constraints oficiales).
├── requirements.txt         great_expectations==1.24.0, pandas, pyarrow, psycopg2, sqlalchemy, matplotlib.
├── .env.example             Variables requeridas SIN credenciales reales. Copiar a .env (ignorado por git).
├── .gitignore               Excluye .env, staging, cachés.
├── dags/
│   └── reliable_music_pipeline.py   DAG (TaskFlow, `from airflow.sdk import dag, task`). SOLO orquesta: dependencias,
│                                    retries por tarea, política de fallos, parámetros. No contiene lógica de datos.
├── src/                     Lógica reutilizable (importada por el DAG):
│   ├── config.py            Rutas y conexiones (variables de entorno).
│   ├── extract.py           extract_spotify (CSV) y extract_grammys (PostgreSQL). Extrae SIN limpiar. Fault injection de pruebas.
│   ├── rules.py             Las 30 reglas de calidad (fuente única): dimensión, umbral, severidad, requisito + su Expectation GX.
│   ├── validation.py        Motor GX: Suite → Validation Definition → Checkpoint; aplica la política Critical/Warning/Info; escribe JSON.
│   ├── transform.py         Limpieza + normalización + integración Spotify↔Grammy + reconciliación (T-01…T-08).
│   ├── load.py              Carga atómica al DW (truncate-and-load en 1 transacción) + vistas KPI + bitácora.
│   └── errors.py            DataQualityError (determinista, sin retry) / IntegrationError.
├── sql/
│   ├── init_databases.sql   Crea las bases grammy_source y music_dw (solo al primer arranque).
│   ├── source_setup.sql     Tabla operacional grammy_awards (preparación de la fuente).
│   ├── dw_schema.sql        Esquema en estrella ejecutable (dims, hecho, constraints, bitácora).
│   └── kpi_queries.sql      4 vistas de KPIs que consume el BI.
├── .gitattributes           Fuerza LF en los archivos (evita roturas CRLF de Git en Windows al montarlos en Docker).
├── scripts/
│   ├── windows/setup.ps1      Crea .env con claves aleatorias (PowerShell).
│   ├── windows/trigger.ps1    Dispara el DAG con parámetros sin problemas de comillas en PowerShell.
│   ├── load_grammy_source.py  Carga el CSV a PostgreSQL + conciliación de filas (evidencia EV-01).
│   ├── dw_snapshot.py         Foto del DW (conteos, medidas, checksum) y `compare` para el rerun seguro.
│   ├── make_charts.py         3 gráficos de KPIs desde el DW (evidencia / respaldo del dashboard).
│   └── export_quality_docs.py Regenera docs/quality_rules.md y gx_expectation_map.md desde src/rules.py.
├── notebooks/data_profiling.ipynb   Profiling reproducible (ya ejecutado) → tabla de riesgos.
├── gx/                      Contexto de Great Expectations (suites, validation definitions, checkpoints) — se crea/actualiza solo.
├── data/raw/                CSV originales (intactos).  data/staging/<batch_id>/  Parquet intermedios por lote.
└── docs/                    architecture, analytical_requirements, quality_risks, quality_rules, gx_expectation_map,
                             transformation_decisions, dimensional_model, failure_policy, traceability_matrix, evidence/.
```

## 5. Arquitectura del pipeline
```
Spotify CSV ─► extract_spotify ─► validate_spotify_raw ─┐
                                                         ├─► transform_and_integrate ─► validate_prepared ─► load_dw ─► DW ─► KPIs/Dashboard
Grammy PostgreSQL ─► extract_grammys ─► validate_grammys_raw ─┘
```
Diagramas Mermaid, tabla de tareas y retries: [`docs/architecture.md`](docs/architecture.md).

## 6. Hallazgos del profiling (resumen)
Evidencia completa y reproducible: `notebooks/data_profiling.ipynb` · [`docs/quality_risks.md`](docs/quality_risks.md).
* Spotify: 450 pares `(track_id, track_genre)` repetidos; `track_id` repetido es **esperado** (misma canción en varios géneros); 157 `tempo=0` y 163 `time_signature=0`; 1 fila sin artista/título; 30,075 filas con varios artistas en un string.
* Grammy: 38.25% de `artist` nulo (crédito en `workers`); **`winner` = True en el 100%** (no se puede distinguir ganador de nominado); `published_at/updated_at` son metadatos web (4/10 valores).
* Cruce: sin llave común; la coincidencia mejora con normalización y tokenización de créditos compuestos.

## 7. Riesgos y reglas de calidad
30 reglas (10 Spotify raw · 9 Grammy raw · 11 prepared) con dimensión, umbral justificado, severidad y requisito:
[`docs/quality_rules.md`](docs/quality_rules.md) (generado desde `src/rules.py`). Los umbrales parten de lo observado **con margen de ingeniería justificado**, no de "lo que pasa hoy".

## 8. Diseño de Great Expectations
`Data Source pandas → Data Asset → Batch Definition (dataframe completo) → Expectation Suite → Validation Definition → Checkpoint`, una por capa
(`spotify_raw`, `grammys_raw`, `prepared`). Cada Expectation lleva `meta={rule_id, severity}` → mapeo regla↔expectation en
[`docs/gx_expectation_map.md`](docs/gx_expectation_map.md). Cada ejecución guarda un JSON por capa con éxito global **y evidencia por regla**
(`observed_value`, `unexpected_count`, `unexpected_percent`) en `docs/evidence/runs/<batch_id>/validation_<capa>.json`.
Política: **Critical** ⇒ la tarea falla y bloquea el downstream · **Warning** ⇒ se registra y continúa · **Informational** ⇒ monitoreo.
La validación **nunca modifica** los datos.

## 9. Estrategia de transformación e integración
Ocho reglas (T-01…T-08) y el **contrato de integración** (llaves, cardinalidad many-to-one, no coincidentes, ambigüedades, límites):
[`docs/transformation_decisions.md`](docs/transformation_decisions.md).

## 10. Modelo dimensional
Estrella con **grano = una pista (`track_id`) en un género**; dimensiones `dim_track`, `dim_artist`, `dim_genre`, `dim_recognition`; hecho `fact_track_listing`.
[`docs/dimensional_model.md`](docs/dimensional_model.md) · DDL: `sql/dw_schema.sql`.

## 11. Diseño del DAG de Airflow
7 tareas, 2 ramas independientes que convergen. Interfaz entre tareas = rutas + metadatos compactos (los datos viajan por Parquet).
Parámetros del run: `batch_id`, `fault_injection`, `simulate_transient`. Tabla completa en [`docs/architecture.md`](docs/architecture.md).

## 12. Política de fallos y reintentos
Retries **selectivos** (no `retries=3` global): extract Grammy 3×20 s exponencial · extract Spotify 1×10 s · `load_dw` 2×30 s · gates y transform **sin retry** (fallas deterministas).
Tabla de condición/respuesta/justificación: [`docs/failure_policy.md`](docs/failure_policy.md).

## 13. Cómo ejecutarlo en Windows (ruta `C:\Users\MATIZ\workshop-2`)

> Todo el pipeline corre **dentro de Docker (Linux)**; Windows solo aporta Docker Desktop, PowerShell y tu navegador.
> Los comandos son para **PowerShell**. Rutas dentro de los contenedores (`/opt/airflow/...`) no cambian.

### 13.0 Requisitos previos (una sola vez)
1. **Docker Desktop** con backend **WSL 2** (Settings → General → *Use the WSL 2 based engine*). Recomendado: ≥ 6 GB de RAM para Docker (Settings → Resources, o `%UserProfile%\.wslconfig` con `memory=6GB`).
2. **Compartir la unidad:** `C:\Users` ya viene compartida por defecto. Si moviste el proyecto a otra unidad, actívala en *Settings → Resources → File sharing*.
3. **Git para Windows** y **Python 3.12** (solo para el notebook y los scripts locales; el pipeline no los necesita).
4. Descomprime el ZIP para que la carpeta quede exactamente en `C:\Users\MATIZ\workshop-2`. Evita OneDrive/Desktop/Documents (sincronización y rutas largas pueden dar problemas).
```powershell
cd C:\Users\MATIZ\workshop-2
docker --version; docker compose version        # verifica que Docker responde
```

### 13.1 Configurar variables (una sola vez)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup.ps1
```
Copia `.env.example` → `.env` y genera `AIRFLOW_JWT_SECRET` y `AIRFLOW_FERNET_KEY` aleatorias (UTF-8 sin BOM). `.env` está en `.gitignore`: **no se sube a GitHub**.
*(Manual: `Copy-Item .env.example .env` y reemplazar las dos claves con los comandos que indica el archivo.)*

### 13.2 Levantar el entorno
```powershell
docker compose up -d --build                    # primer build: varios minutos
docker compose ps                               # warehouse-db, airflow-db y airflow-apiserver deben quedar 'healthy'
docker compose exec airflow-scheduler airflow version     # debe imprimir 3.1.8   (EV-14)
```
UI de Airflow: **http://localhost:8080** (sin login: modo desarrollo local). Si el puerto 8080 o 5433 ya está ocupado en tu PC, cambia el puerto en `docker-compose.yaml`/`.env` (`WAREHOUSE_HOST_PORT`).

### 13.3 Preparar la fuente relacional de Grammy (NO es la carga ETL)
```powershell
docker compose exec airflow-scheduler python scripts/load_grammy_source.py
docker compose exec warehouse-db psql -U etl_user -d grammy_source -c "select count(*) from grammy_awards;"    # 4810
```
Crea `grammy_source.public.grammy_awards` y escribe `docs\evidence\source_preparation.json` (filas CSV = filas tabla + sha256).

### 13.4 Perfilado (el notebook ya viene ejecutado; esto es para reproducirlo)
```powershell
cd C:\Users\MATIZ\workshop-2
python -m venv .venv
.\.venv\Scripts\Activate.ps1                    # si PowerShell lo bloquea: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt jupyterlab
jupyter lab notebooks\data_profiling.ipynb      # desde Windows la BD está en localhost:5433 (defaults de src/config.py)
```

### 13.5 Prueba A · Ejecución exitosa
```powershell
.\scripts\windows\trigger.ps1                   # batch_001, sin fallas
docker compose exec airflow-scheduler airflow dags list-runs reliable_music_pipeline
```
(o en la UI: **Dags → reliable_music_pipeline → Trigger**). Esperado: 7 tareas en **success**. Evidencia en `docs\evidence\runs\batch_001\`. `validate_grammys_raw` termina `PASS_WITH_WARNINGS` por **DQ-G07** (esperado y documentado).

### 13.6 Prueba B · Falla Critical controlada
```powershell
.\scripts\windows\trigger.ps1 -BatchId batch_fail_001 -Fault spotify_null_track_id       # viola DQ-S01
.\scripts\windows\trigger.ps1 -BatchId batch_fail_002 -Fault grammy_invalid_year         # viola DQ-G02 (opcional)
```
Esperado: `validate_*_raw` **failed**, y `transform_and_integrate`, `validate_prepared`, `load_dw` en **upstream_failed**; el DW no cambia. Evidencia: Graph/Grid, log de la tarea y `docs\evidence\runs\batch_fail_001\validation_spotify_raw.json`.

> **¿Por qué un `.ps1` para disparar?** PowerShell 5.1 elimina las comillas dobles al pasar JSON a `docker compose exec`, y `--conf '{"batch_id":...}'` llega roto. El script codifica el JSON en base64 y lo decodifica dentro del contenedor. Desde la UI no hay este problema.

### 13.7 Retry selectivo y carga atómica
```powershell
.\scripts\windows\trigger.ps1 -Transient extract_grammys      # falla el intento 1 y se reintenta
.\scripts\windows\trigger.ps1 -Transient load_dw              # falla a mitad de carga (ROLLBACK) y se reintenta limpio
```
UI: *Task Instance → Tries* muestra intento 1 `failed/up_for_retry` e intento 2 `success`.

### 13.8 Rerun seguro (mismo lote, sin duplicados)
```powershell
docker compose exec airflow-scheduler python scripts/dw_snapshot.py antes
.\scripts\windows\trigger.ps1                                   # mismo batch_001   (espera a que termine)
docker compose exec airflow-scheduler python scripts/dw_snapshot.py despues
docker compose exec airflow-scheduler python scripts/dw_snapshot.py compare antes despues      # -> IDÉNTICO
```

### 13.9 Dashboard (consultando el DW, no los CSV)
* **Power BI Desktop (Windows):** *Obtener datos → Base de datos PostgreSQL* → Servidor `localhost:5433`, Base `music_dw`, credenciales de tu `.env` (`WAREHOUSE_USER`/`WAREHOUSE_PASSWORD`). Si pide el conector Npgsql, instálalo desde el aviso de Power BI. Selecciona `vw_kpi_popularity_by_recognition`, `vw_kpi_genre_grammy_share`, `vw_kpi_popularity_by_grammy_decade` y `vw_kpi_summary`.
* **Metabase (opcional, confirmar con el docente):** `docker compose --profile bi up -d` → http://localhost:3000 → PostgreSQL: host `warehouse-db`, puerto `5432`, db `music_dw`.
* **Respaldo reproducible:** `docker compose exec airflow-scheduler python scripts/make_charts.py` → `docs\evidence\dashboard\*.png`.

### 13.10 Detener / reiniciar de cero
```powershell
docker compose down            # detiene (conserva datos)
docker compose down -v         # borra BD, metadatos y logs (repetir 13.2-13.3)
```

### 13.11 Subir a GitHub
```powershell
cd C:\Users\MATIZ\workshop-2
git init; git add .; git status                 # verifica que .env NO aparece en la lista
git commit -m "Workshop-2: reliable batch pipeline"
git branch -M main; git remote add origin https://github.com/<tu-usuario>/<repo>.git; git push -u origin main
```
`.gitattributes` fuerza saltos de línea LF para que los archivos no se rompan dentro de Linux/Docker.

### 13.12 Problemas típicos en Windows
| Síntoma | Causa / solución |
|---|---|
| `docker compose` no responde / `error during connect` | Docker Desktop no está iniciado (esperar a "Engine running"). |
| Contenedores se reinician o `airflow-init` falla | Poca RAM: subir a ≥ 6 GB en Docker/WSL. |
| `.env` sin efecto o error de variable | Guardado con BOM o CRLF: usa `setup.ps1` (UTF-8 sin BOM). |
| `Bind for 0.0.0.0:8080/5433 failed: port is already allocated` | Otro programa usa el puerto (p. ej. un Postgres local en 5432/5433): cambia el puerto publicado. |
| Error de permisos al escribir en `data\`/`docs\` | Reiniciar Docker Desktop y verificar *File sharing*; no usar carpetas de OneDrive. |
| `UnicodeDecodeError`/caracteres raros al correr scripts locales | Ya cubierto: todo el código lee/escribe UTF-8. Si usas otro script propio, añade `encoding="utf-8"`. |
| `running scripts is disabled on this system` | `powershell -ExecutionPolicy Bypass -File ...` o `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |

> **Linux/macOS:** los mismos comandos `docker compose ...` funcionan; en lugar de los `.ps1` usa `airflow dags trigger ... --conf '{"batch_id":"batch_001"}'` y, solo en Linux, `AIRFLOW_UID=$(id -u)` y `chmod -R a+rwX data docs gx`.

## 14. Resultados de referencia (verificación del repositorio)
Verificado de punta a punta con Airflow 3.1.8 + PostgreSQL 16 + GX 1.24 (salidas en `docs/evidence/reference_run/`):
| Prueba | Resultado |
|---|---|
| A · éxito | 7/7 tareas `success`; DW: 113,549 hechos · 89,740 pistas · 17,627 artistas · 114 géneros |
| B · falla Critical | `validate_spotify_raw` **failed** (DQ-S01); transform/validate_prepared/load **no se ejecutan**; DW intacto |
| Retry `extract_grammys` | intento 1 `up_for_retry` → intento 2 `success` |
| Falla a mitad de `load_dw` | ROLLBACK → reintento exitoso; DW idéntico |
| Rerun seguro | conteos, medidas y checksum **idénticos** antes/después |

KPIs obtenidos (para tu análisis; interprétalos tú con criterio): popularidad promedio *No Grammy link* 33.51 · *Artist Grammy-linked* 30.94 · *Track Grammy-linked* 41.36.
La popularidad por década del primer Grammy es baja para los 50s (n=8 artistas) y se estabiliza en 33–35 desde los 90s — con n pequeño en las primeras décadas, **no sobreinterpretes**.

## 15. Supuestos y limitaciones
1. El vínculo se hace por **nombre** (no por identificador): homónimos pueden dar falsos positivos; solo se vincula el **primer** artista acreditado.
2. 38% de las nominaciones Grammy no tiene `artist` (crédito en `workers`) y no se vincula; la tasa de coincidencia (47.87% de las nominaciones con artista) es una cota inferior.
3. `winner` es siempre True: se habla de "vinculado a Grammy", no de "ganador".
4. Spotify no tiene fecha: la dimensión temporal proviene solo del Grammy (AR-3).
5. `popularity` es un valor de un instante de Spotify, no histórico.
6. Modo sin login de Airflow y credenciales de ejemplo: **solo para desarrollo local**.
7. Fault injection (`fault_injection`, `simulate_transient`) existe únicamente para demostrar las pruebas B/retry; con `none` (por defecto) no altera nada.

## 16. Qué debes completar tú antes de entregar
- [ ] Ejecutar 13.1–13.8 en tu máquina y tomar **tus** capturas (EV-07, EV-09, EV-10, EV-14), recortadas e interpretadas, en `docs/evidence/` (`docs/evidence/README.md` es el registro).
- [ ] Construir el dashboard en Power BI/Tableau/Looker Studio (o Metabase aprobado) y capturarlo (EV-13).
- [ ] Hacer `git init`, commit y push a GitHub (verifica que `.env` **no** se sube).
- [ ] Preparar la defensa: explicar la cadena requisito → riesgo → regla → expectation → transformación → DW → KPI (`docs/traceability_matrix.md`).
