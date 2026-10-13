# Mapeo Rule ID → Great Expectations

Cada Expectation lleva `meta={rule_id, severity}`. Suites: `spotify_raw_suite`, `grammys_raw_suite`, `prepared_suite` (en `gx/expectations/`). Validation Definitions: `<capa>_validation`. Checkpoints: `<capa>_checkpoint`.

| Rule ID | Suite | Expectation GX | Parámetros clave | Severidad |
|---|---|---|---|---|
| DQ-S01 | spotify_raw_suite | `expect_column_values_to_not_be_null` | column=track_id | Critical |
| DQ-S02 | spotify_raw_suite | `expect_table_columns_to_match_set` | column_set=['track_id', 'artists', 'album_name', 'track_name', 'popularity', 'duration_ms', 'explicit', 'danceability', 'energy', 'key', 'loudness', 'mode', 'sp | Critical |
| DQ-S03 | spotify_raw_suite | `expect_column_values_to_not_be_null` | column=popularity | Critical |
| DQ-S03 | spotify_raw_suite | `expect_column_values_to_be_between` | column=popularity, min_value=0.0, max_value=100.0 | Critical |
| DQ-S04 | spotify_raw_suite | `expect_column_values_to_be_between` | column=danceability, min_value=0.0, max_value=1.0 | Critical |
| DQ-S04 | spotify_raw_suite | `expect_column_values_to_be_between` | column=energy, min_value=0.0, max_value=1.0 | Critical |
| DQ-S04 | spotify_raw_suite | `expect_column_values_to_be_between` | column=valence, min_value=0.0, max_value=1.0 | Critical |
| DQ-S05 | spotify_raw_suite | `expect_compound_columns_to_be_unique` | column_list=['track_id', 'track_genre'], mostly=0.98 | Warning |
| DQ-S06 | spotify_raw_suite | `expect_column_values_to_be_between` | column=tempo, mostly=0.995, min_value=0.0, strict_min=True | Warning |
| DQ-S06 | spotify_raw_suite | `expect_column_values_to_be_between` | column=time_signature, mostly=0.995, min_value=1.0, max_value=7.0 | Warning |
| DQ-S07 | spotify_raw_suite | `expect_column_values_to_not_be_null` | column=artists, mostly=0.999 | Warning |
| DQ-S07 | spotify_raw_suite | `expect_column_values_to_not_be_null` | column=track_name, mostly=0.999 | Warning |
| DQ-S08 | spotify_raw_suite | `expect_table_row_count_to_be_between` | min_value=50000, max_value=500000 | Critical |
| DQ-S09 | spotify_raw_suite | `expect_column_value_lengths_to_equal` | column=track_id, value=22.0 | Critical |
| DQ-S10 | spotify_raw_suite | `expect_column_unique_value_count_to_be_between` | column=track_genre, min_value=100, max_value=150 | Informational |
| DQ-G01 | grammys_raw_suite | `expect_table_columns_to_match_set` | column_set=['year', 'title', 'published_at', 'updated_at', 'category', 'nominee', 'artist', 'workers', 'img', 'winner'], exact_match=False | Critical |
| DQ-G02 | grammys_raw_suite | `expect_column_values_to_not_be_null` | column=year | Critical |
| DQ-G02 | grammys_raw_suite | `expect_column_values_to_be_between` | column=year, min_value=1958.0, max_value=2030.0 | Critical |
| DQ-G03 | grammys_raw_suite | `expect_column_values_to_not_be_null` | column=category | Critical |
| DQ-G04 | grammys_raw_suite | `expect_column_values_to_not_be_null` | column=nominee, mostly=0.99 | Warning |
| DQ-G05 | grammys_raw_suite | `expect_column_values_to_not_be_null` | column=artist, mostly=0.55 | Warning |
| DQ-G06 | grammys_raw_suite | `expect_compound_columns_to_be_unique` | column_list=['year', 'category', 'nominee', 'artist'], mostly=0.999 | Warning |
| DQ-G07 | grammys_raw_suite | `expect_column_distinct_values_to_contain_set` | column=winner, value_set=[True, False] | Warning |
| DQ-G08 | grammys_raw_suite | `expect_table_row_count_to_be_between` | min_value=1000, max_value=20000 | Critical |
| DQ-G09 | grammys_raw_suite | `expect_column_unique_value_count_to_be_between` | column=category, min_value=400, max_value=900 | Informational |
| DQ-P01 | prepared_suite | `expect_table_columns_to_match_set` | column_set=['track_id', 'track_genre', 'track_name', 'album_name', 'artists_raw', 'primary_artist', 'primary_artist_norm', 'n_artists', 'explicit', 'popularity' | Critical |
| DQ-P02 | prepared_suite | `expect_column_values_to_not_be_null` | column=track_id | Critical |
| DQ-P02 | prepared_suite | `expect_column_values_to_not_be_null` | column=track_genre | Critical |
| DQ-P02 | prepared_suite | `expect_column_values_to_not_be_null` | column=primary_artist_norm | Critical |
| DQ-P03 | prepared_suite | `expect_compound_columns_to_be_unique` | column_list=['track_id', 'track_genre'] | Critical |
| DQ-P04 | prepared_suite | `expect_column_values_to_be_in_set` | column=recognition_level, value_set=['No Grammy link', 'Artist Grammy-linked', 'Track Grammy-linked'] | Critical |
| DQ-P05 | prepared_suite | `expect_column_values_to_not_be_null` | column=popularity | Critical |
| DQ-P05 | prepared_suite | `expect_column_values_to_be_between` | column=popularity, min_value=0.0, max_value=100.0 | Critical |
| DQ-P06 | prepared_suite | `expect_column_values_to_be_between` | column=tempo, min_value=30.0, max_value=260.0 | Critical |
| DQ-P06 | prepared_suite | `expect_column_values_to_be_between` | column=time_signature, min_value=1.0, max_value=7.0 | Critical |
| DQ-P06 | prepared_suite | `expect_column_values_to_be_between` | column=duration_ms, min_value=1.0 | Critical |
| DQ-P07 | prepared_suite | `expect_table_row_count_to_equal` | value=0 | Critical |
| DQ-P08 | prepared_suite | `expect_column_pair_values_a_to_be_greater_than_b` | column_A=grammy_artist_linked, column_B=grammy_track_linked, or_equal=True | Critical |
| DQ-P09 | prepared_suite | `expect_column_sum_to_be_between` | column=grammy_artist_linked, min_value=1000.0 | Critical |
| DQ-P10 | prepared_suite | `expect_column_sum_to_be_between` | column=grammy_track_linked, min_value=100.0 | Warning |
| DQ-P11 | prepared_suite | `expect_column_mean_to_be_between` | column=grammy_artist_linked, min_value=0.01, max_value=0.6 | Informational |
