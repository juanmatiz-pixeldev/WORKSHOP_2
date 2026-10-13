-- ============================================================================
-- sql/source_setup.sql  ·  PREPARACIÓN DE LA FUENTE (NO es la carga ETL al DW)
-- Base: grammy_source.  Crea la tabla operacional que el pipeline EXTRAE.
-- Decisiones de preparación:
--   * Las columnas se guardan tal cual vienen en el CSV (published_at/updated_at
--     como TEXT) para NO ocultar problemas de calidad de la fuente.
--   * source_row_id es una llave técnica de linaje (no existe en el CSV).
--   * Sin NOT NULL ni CHECK: la fuente es "sucia" a propósito; la calidad se
--     verifica en la compuerta validate_grammys_raw, no aquí.
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.grammy_awards (
    source_row_id  SERIAL PRIMARY KEY,
    year           INTEGER,
    title          TEXT,
    published_at   TEXT,
    updated_at     TEXT,
    category       TEXT,
    nominee        TEXT,
    artist         TEXT,
    workers        TEXT,
    img            TEXT,
    winner         BOOLEAN
);
