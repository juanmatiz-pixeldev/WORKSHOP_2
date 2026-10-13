-- Se ejecuta UNA sola vez, al crear el volumen de Postgres (docker-entrypoint-initdb.d).
-- Crea las dos bases del contenedor "warehouse-db":
--   grammy_source : base relacional OPERACIONAL de donde el pipeline extrae Grammy
--   music_dw      : Data Warehouse dimensional (destino de la carga ETL)
CREATE DATABASE grammy_source;
CREATE DATABASE music_dw;
