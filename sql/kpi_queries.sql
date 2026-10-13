-- ============================================================================
-- sql/kpi_queries.sql · KPIs del dashboard (se materializan como VISTAS)
-- Todas leen SOLO el Data Warehouse (music_dw). El BI se conecta a estas vistas.
-- ============================================================================

-- KPI-1 · AR-1: ¿Los artistas/pistas con vínculo Grammy son más populares?
CREATE OR REPLACE VIEW vw_kpi_popularity_by_recognition AS
SELECT r.recognition_level,
       COUNT(*)                          AS listings,
       COUNT(DISTINCT f.track_key)       AS distinct_tracks,
       ROUND(AVG(f.popularity)::numeric, 2)   AS avg_popularity,
       ROUND(AVG(f.danceability)::numeric, 3) AS avg_danceability,
       ROUND(AVG(f.energy)::numeric, 3)       AS avg_energy,
       ROUND(AVG(f.valence)::numeric, 3)      AS avg_valence
FROM fact_track_listing f
JOIN dim_recognition r USING (recognition_key)
GROUP BY r.recognition_level, r.sort_order
ORDER BY r.sort_order;

-- KPI-2 · AR-2: ¿Qué géneros concentran más pistas con vínculo Grammy?
CREATE OR REPLACE VIEW vw_kpi_genre_grammy_share AS
SELECT g.genre_name,
       COUNT(*)                                                    AS listings,
       COUNT(*) FILTER (WHERE r.recognition_level <> 'No Grammy link') AS grammy_linked_listings,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.recognition_level <> 'No Grammy link')
             / COUNT(*), 2)                                        AS grammy_share_pct
FROM fact_track_listing f
JOIN dim_genre g USING (genre_key)
JOIN dim_recognition r USING (recognition_key)
GROUP BY g.genre_name
HAVING COUNT(*) >= 100;

-- KPI-3 · AR-3: ¿Cambia la popularidad según la década del primer Grammy del artista?
CREATE OR REPLACE VIEW vw_kpi_popularity_by_grammy_decade AS
SELECT a.first_grammy_decade,
       COUNT(DISTINCT a.artist_key)           AS artists,
       COUNT(*)                               AS listings,
       ROUND(AVG(f.popularity)::numeric, 2)   AS avg_popularity
FROM fact_track_listing f
JOIN dim_artist a USING (artist_key)
WHERE a.is_grammy_artist
GROUP BY a.first_grammy_decade
ORDER BY a.first_grammy_decade;

-- KPI cards (resumen general)
CREATE OR REPLACE VIEW vw_kpi_summary AS
SELECT COUNT(*)                                              AS total_listings,
       COUNT(DISTINCT f.track_key)                           AS total_tracks,
       COUNT(DISTINCT f.artist_key)                          AS total_artists,
       COUNT(DISTINCT f.artist_key) FILTER (WHERE a.is_grammy_artist) AS grammy_artists,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.recognition_level <> 'No Grammy link')
             / COUNT(*), 2)                                  AS grammy_linked_listing_pct,
       ROUND(AVG(f.popularity)::numeric, 2)                  AS avg_popularity
FROM fact_track_listing f
JOIN dim_artist a USING (artist_key)
JOIN dim_recognition r USING (recognition_key);
