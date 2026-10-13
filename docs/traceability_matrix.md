# Matriz de trazabilidad de extremo a extremo (Sección 8.2)

| Requisito | Datos requeridos | Riesgo de calidad | Regla DQ | GX Expectation | Transformación | Elemento DW | KPI / Visualización |
|---|---|---|---|---|---|---|---|
| AR-1 | Spotify `popularity`, `artists`, `track_name`; Grammy `artist`, `nominee` | Pistas duplicadas por género inflan conteos | DQ-S05, DQ-P03 | `expect_compound_columns_to_be_unique` | T-03 deduplicar `(track_id, track_genre)` | `fact_track_listing` (UNIQUE track_key+genre_key) | KPI-1 · barras de popularidad por nivel |
| AR-1 | Spotify `popularity` | Popularidad fuera de rango/nula | DQ-S03, DQ-P05 | `expect_column_values_to_be_between`, `…not_be_null` | (se valida; sin modificar) | `fact.popularity` (CHECK 0-100) | KPI-1 |
| AR-1 | Spotify `tempo`, `time_signature` | Ceros centinela imposibles | DQ-S06 (Warning), DQ-P06 (Critical) | `expect_column_values_to_be_between` | T-02 centinela → NULL | `fact.tempo` (CHECK >0) | KPI-1 (audio features) |
| AR-1/2/3 | Artista en ambas fuentes | Créditos compuestos y mayúsculas impiden el cruce | DQ-P07, DQ-P08, DQ-P09 | `expect_table_row_count_to_equal`, `expect_column_pair_values_a_to_be_greater_than_b`, `expect_column_sum_to_be_between` | T-05, T-06, T-07, T-08 | `dim_artist`, `dim_recognition` | KPI-1, KPI-2, KPI-3 |
| AR-2 | Spotify `track_genre` | Taxonomía de géneros cambia | DQ-S10 (Info) | `expect_column_unique_value_count_to_be_between` | T-06 (género en minúsculas) | `dim_genre` | KPI-2 · top géneros Grammy |
| AR-3 | Grammy `year` | Año imposible corrompe la década | DQ-G02 (Critical) | `expect_column_values_to_be_between` | derivar `first_grammy_decade` | `dim_artist.first_grammy_decade` | KPI-3 · línea por década |
| AR-1 | Grammy `winner` | `winner` siempre True: no hay "no ganadores" | DQ-G07 (Warning) | `expect_column_distinct_values_to_contain_set` | (límite documentado; no se usa winner como discriminante) | — | Nota en dashboard |
| AR-1/2/3 | Grammy `artist` | 38% nulo | DQ-G05 (Warning) | `expect_column_values_to_not_be_null (mostly=0.55)` | T-07 (solo tokeniza si hay artista) | `recognition_level = No Grammy link` para no vinculados | Limitación en KPI-2 |

Mapeo completo de las 30 reglas: `docs/quality_rules.md` y `docs/gx_expectation_map.md`.
