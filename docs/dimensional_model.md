# Modelo dimensional (Sección 6.4)

```mermaid
erDiagram
    fact_track_listing }o--|| dim_track : track_key
    fact_track_listing }o--|| dim_artist : artist_key
    fact_track_listing }o--|| dim_genre : genre_key
    fact_track_listing }o--|| dim_recognition : recognition_key
    fact_track_listing {
        bigint track_listing_key PK
        int track_key FK
        int artist_key FK
        int genre_key FK
        smallint recognition_key FK
        text batch_id
        smallint popularity
        int duration_ms
        real danceability
        real energy
        real valence
        real tempo
    }
    dim_track { int track_key PK  char22 track_id UK  text track_name  text artists_raw  boolean explicit  int track_grammy_nominations }
    dim_artist { int artist_key PK  text artist_norm UK  text artist_name  boolean is_grammy_artist  int grammy_nominations  int first_grammy_year  text first_grammy_decade }
    dim_genre { int genre_key PK  text genre_name UK }
    dim_recognition { smallint recognition_key PK  text recognition_level UK }
```

| Decisión | Contenido |
|---|---|
| **Proceso de negocio** | Presencia de pistas de Spotify en géneros, enriquecida con el reconocimiento Grammy del artista/canción. |
| **Grano** | **Una fila = una pista de Spotify (`track_id`) en un género (`track_genre`)**. Es el grano de la fuente tras deduplicar el par. |
| **Dimensiones** | `dim_track` (qué pista), `dim_artist` (artista principal + atributos Grammy), `dim_genre`, `dim_recognition` (3 niveles: *No Grammy link*, *Artist Grammy-linked*, *Track Grammy-linked*). |
| **Medidas** | `popularity`, `duration_ms`, `danceability`, `energy`, `valence`, `acousticness`, `instrumentalness`, `liveness`, `speechiness`, `loudness`, `tempo` (todas a nivel pista-género; tempo/duración admiten NULL). |
| **Llaves** | PK surrogate entera (SERIAL) en cada dimensión y en el hecho; **business keys** con UNIQUE: `track_id`, `artist_norm`, `genre_name`, `recognition_level`. FKs con integridad referencial en el hecho. |
| **Restricciones** | `UNIQUE(track_key, genre_key)` en el hecho (impide duplicados en reruns); `CHECK popularity 0-100`; `CHECK tempo > 0`. |
| **Bitácora** | `etl_batch_log` (no se trunca): lote, fecha, estado y conteos de cada carga. |

**Atributos Grammy en `dim_artist`:** `is_grammy_artist`, `grammy_nominations`, `grammy_wins`, `first_grammy_year`, `first_grammy_decade`
(derivados de la integración; se tratan como atributos descriptivos del artista, tipo SCD-1).

## Cómo cada requisito queda soportado

| Requisito | Hecho / dimensiones | Consulta (vista) |
|---|---|---|
| AR-1 | `fact_track_listing` ⨝ `dim_recognition` | `vw_kpi_popularity_by_recognition` |
| AR-2 | `fact_track_listing` ⨝ `dim_genre` ⨝ `dim_recognition` | `vw_kpi_genre_grammy_share` |
| AR-3 | `fact_track_listing` ⨝ `dim_artist` (`first_grammy_decade`) | `vw_kpi_popularity_by_grammy_decade` |

DDL ejecutable: `sql/dw_schema.sql`. Vistas: `sql/kpi_queries.sql`.
