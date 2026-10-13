# Registro de decisiones de transformación e integración (Sección 6.8)

Una sola fase (`transform_and_integrate`, código en `src/transform.py`). Cada decisión es defendible **independientemente**
del resultado de la validación (no se modifica nada "para pasar" un check).

| ID | Regla y justificación | Campos afectados | Antes → Después | Manejo de excepciones | Impacto analítico |
|---|---|---|---|---|---|
| T-01 | Quitar columna índice exportada por pandas; no es un atributo del negocio. *(Perfilado: `Unnamed: 0` = 0..113999)* | Spotify `Unnamed: 0` | 21 → 20 columnas | — | Mantiene limpio el esquema del DW |
| T-02 | Valores centinela imposibles → `NULL` (0 BPM, compás 0, duración 0 significan "no detectado"). **No se borran filas.** *(157 tempo=0, 163 time_signature=0)* | `tempo`, `time_signature`, `duration_ms` | `0` → `NULL` | Si no es convertible, queda NULL y se reporta en `reconciliation.json` | Evita promedios de tempo sesgados (AR-1) |
| T-03 | Deduplicar el grano `(track_id, track_genre)`, conservando la fila de mayor popularidad. *(450 pares repetidos)* | Spotify (filas) | 113,999 → 113,549 | Conteo removido registrado | Evita doble conteo y viola-UNIQUE del hecho |
| T-04 | Filas sin `track_id/artists/track_name/popularity` → **cuarentena** (`spotify_quarantine.parquet`), no integrables. *(1 fila)* | Spotify (filas) | 114,000 → 113,999 | Archivo de cuarentena + conteo | Conserva trazabilidad del descarte |
| T-05 | Separar `artists` por `;` y tomar el **primer** artista como `primary_artist` (artista principal asumido) | `artists` → `primary_artist`, `n_artists` | `"A;B"` → `A`, 2 | — | Llave de integración (AR-1..3) |
| T-06 | Normalizar nombres: quitar acentos, `casefold`, `&`→`and`, puntuación, prefijo `the`; para títulos además quitar `(feat…)`, `[…]`, `- Remastered` | `primary_artist_norm`, `track_key_norm`, `nominee_key` | `"Beyoncé"` → `beyonce` | Si la normalización queda vacía (p. ej. nombres no latinos), se conserva el texto casefold original | Reduce falsos negativos de emparejamiento (517 → 551 artistas exactos vs normalizados) |
| T-07 | Dividir créditos Grammy compuestos (`&`, `and`, `featuring`, `with`, `,`, `/`). Si el crédito **completo** ya existe como artista Spotify (p. ej. *Earth, Wind & Fire*) se usa entero; las partes < 3 letras se descartan | Grammy `artist` → tokens | `"Post Malone & Swae Lee"` → `post malone`, `swae lee` | Créditos sin tokens válidos quedan sin vincular (medido) | 480 créditos compuestos serían inalcanzables sin esta regla |
| T-08 | Integración y derivación de `recognition_level` y atributos Grammy (ver contrato) | columnas Grammy → Spotify | — | — | Habilita AR-1, AR-2, AR-3 |
| T-09 | Descartar `img`, `title`, `published_at`, `updated_at`, `workers` de Grammy | Grammy | — | — | `published_at/updated_at` solo tienen 4/10 valores (metadatos web), no son fecha del premio |

## Contrato de integración

| Ítem | Decisión y evidencia |
|---|---|
| **Llaves** | Artista: `primary_artist_norm` (Spotify) = `token` (Grammy). Canción: (`primary_artist_norm`, `track_key_norm`) = (`token`, `nominee_key`). |
| **Cardinalidad** | Antes del join, las nominaciones se agregan por token (y por token+título). Resultado: Spotify→artista **many-to-one**, Spotify→canción **many-to-one**. `merge(validate="many_to_one")` lo impone en código y `DQ-P07` verifica que las filas no cambian. Una canción nominada en varias categorías (p. ej. *Record* y *Song of the Year*) cuenta una sola vez con `track_grammy_nominations = n`. |
| **Preprocesamiento** | T-05, T-06, T-07 (normalización y tokenización antes de unir). |
| **Registros sin coincidencia** | Medidos en `reconciliation.json`: nominaciones sin artista (1,840), con artista sin coincidencia en Spotify (1,539 de 2,952), tasa de coincidencia (47.87%). Las pistas sin coincidencia permanecen en el DW como *No Grammy link* (no se descartan). |
| **Coincidencias duplicadas / ambiguas** | Detectadas por `DQ-P03` (unicidad del grano) y `DQ-P07` (conteo igual al esperado). Un artista Spotify homónimo de uno Grammy no puede distinguirse (ver limitaciones). |
| **Supuestos y límites** | (1) Solo se vincula el **primer** artista acreditado. (2) El 38% de las nominaciones carece de `artist` (crédito en `workers`) y no se vincula. (3) Homónimos pueden producir falsos positivos; el match por canción exige artista + título para mitigarlo. (4) `winner` es siempre True: solo se puede afirmar "vinculado a Grammy", no "ganador". (5) El vínculo es por **nombre**, no por identificador estable. |

## Resultados de reconciliación (lote de referencia)

| Métrica | Valor |
|---|---|
| Spotify entrada → salida | 114,000 → 113,549 (450 duplicados, 1 en cuarentena) |
| Centinelas a NULL | tempo 157 · time_signature 163 · duration 0 |
| Nominaciones Grammy con artista que coinciden con un artista Spotify | 1,413 de 2,952 (47.87%) |
| Listados vinculados por artista / por canción | 11,080 (9.76%) / 685 |
| Filas preparadas = filas esperadas | 113,549 = 113,549 ✔ |
