# Requisitos analíticos y alcance (Sección 6.1)

## Declaración de alcance
Se construye un pipeline batch confiable que integra **Spotify** (CSV, 114,000 filas de pistas por género) y **Grammy Awards**
(tabla PostgreSQL, 4,810 nominaciones 1958-2019) en un Data Warehouse dimensional (estrella) para estudiar la relación entre el
**reconocimiento Grammy** y el **desempeño/características de las pistas en Spotify**.
*Dentro del alcance:* vínculo por **artista principal** y por **artista + título de canción**. *Fuera de alcance:* artistas
secundarios (feats), créditos de `workers`, distinción ganador/nominado (el dataset solo trae `winner=True`) y datos temporales de Spotify (no existen).

## Tabla de requisitos

| ID | Requisito analítico (pregunta/decisión) | Datos requeridos | Fuente(s) | KPI(s) esperados | Nivel de detalle |
|---|---|---|---|---|---|
| **AR-1** | ¿Las pistas cuyo artista (o la propia canción) fue reconocido por los Grammy son más populares en Spotify que las demás? → decide si el reconocimiento se asocia con mayor audiencia. | Spotify: `track_id`, `artists`, `track_name`, `popularity`, `danceability`, `energy`, `valence`. Grammy: `artist`, `nominee`. | Spotify + Grammy | **KPI-1** Popularidad promedio por nivel de reconocimiento (No link / Artist-linked / Track-linked) | Pista × género, agregada por nivel de reconocimiento |
| **AR-2** | ¿Qué géneros musicales concentran la mayor proporción de pistas con vínculo Grammy? → orienta en qué géneros el Grammy "mira" más. | Spotify: `track_genre`, `artists`. Grammy: `artist`. | Spotify + Grammy | **KPI-2** % de listados vinculados a Grammy por género (top 15) | Género |
| **AR-3** | ¿Cambia la popularidad actual de los artistas según la década de su **primer** Grammy? → mide si la "época" del reconocimiento importa. | Spotify: `artists`, `popularity`. Grammy: `artist`, `year`. | Spotify + Grammy | **KPI-3** Popularidad promedio y n.º de artistas por década del primer Grammy | Artista (agregado por década) |

**Por qué se necesitan ambas fuentes:** Spotify no sabe de premios y Grammy no sabe de popularidad ni de géneros ni de audio;
cada pregunta cruza un atributo de una con un atributo de la otra (no se puede responder con una sola).

## Trazabilidad
Los IDs `AR-1..3` se usan en: `src/rules.py` (columna *requirements*), `docs/quality_rules.md`, `docs/traceability_matrix.md`,
`sql/kpi_queries.sql` (comentarios de cada vista), `docs/dimensional_model.md` y el README.
