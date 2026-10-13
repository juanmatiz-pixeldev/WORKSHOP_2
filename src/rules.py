"""FUENTE ÚNICA DE VERDAD de las reglas de calidad.

Cada Rule documenta: dimensión de calidad, regla, métrica/umbral, severidad,
requisito analítico y justificación; y sabe construir sus Expectations de
Great Expectations (build). El meta de cada Expectation lleva rule_id + severity,
de modo que el resultado de validación se vincula a la regla (mapeo Rule -> GX).
`scripts/export_quality_docs.py` genera docs/quality_rules.md desde este archivo.
"""
from dataclasses import dataclass, field
from typing import Callable

import great_expectations.expectations as gxe

CRITICAL, WARNING, INFO = "Critical", "Warning", "Informational"

SPOTIFY_REQUIRED = ["track_id", "artists", "album_name", "track_name", "popularity", "duration_ms",
                    "explicit", "danceability", "energy", "key", "loudness", "mode", "speechiness",
                    "acousticness", "instrumentalness", "liveness", "valence", "tempo",
                    "time_signature", "track_genre"]
GRAMMY_REQUIRED = ["year", "title", "published_at", "updated_at", "category", "nominee", "artist",
                   "workers", "img", "winner"]
PREPARED_COLUMNS = ["track_id", "track_genre", "track_name", "album_name", "artists_raw", "primary_artist",
                    "primary_artist_norm", "n_artists", "explicit", "popularity", "duration_ms",
                    "danceability", "energy", "valence", "acousticness", "instrumentalness", "liveness",
                    "speechiness", "loudness", "tempo", "time_signature", "grammy_artist_linked",
                    "grammy_track_linked", "recognition_level", "artist_grammy_nominations",
                    "artist_grammy_wins", "artist_first_grammy_year", "artist_first_grammy_decade",
                    "track_grammy_nominations"]
RECOGNITION_LEVELS = ["No Grammy link", "Artist Grammy-linked", "Track Grammy-linked"]


@dataclass
class Rule:
    rule_id: str
    layer: str               # spotify_raw | grammys_raw | prepared
    attributes: str
    dimension: str
    description: str
    threshold: str
    severity: str
    requirements: str
    justification: str
    build: Callable = field(repr=False, default=lambda ctx: [])


def _m(rule):  # meta común de cada expectation
    return {"rule_id": rule.rule_id, "severity": rule.severity}


RULES: list[Rule] = []


def rule(**kw):
    def deco(fn):
        r = Rule(build=lambda ctx, fn=fn: fn(ctx), **kw)
        RULES.append(r)
        return fn
    return deco


def _R(rid):
    return next(r for r in RULES if r.rule_id == rid)


# ============================ SPOTIFY · RAW ============================
@rule(rule_id="DQ-S01", layer="spotify_raw", attributes="track_id", dimension="Completeness",
      description="Todo registro debe tener track_id (llave de negocio de dim_track).",
      threshold="% no nulos = 100%", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Sin track_id no hay llave de negocio ni deduplicación posible. Perfilado: 0 nulos.")
def _(ctx):
    return [gxe.ExpectColumnValuesToNotBeNull(column="track_id", mostly=1.0, meta=_m(_R("DQ-S01")))]


@rule(rule_id="DQ-S02", layer="spotify_raw", attributes="20 columnas requeridas", dimension="Structure/Validity",
      description="El esquema debe contener todas las columnas requeridas por los requisitos.",
      threshold="Todas presentes (0 faltantes)", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Contrato de la fuente: columna faltante = transformación imposible (falla determinista).")
def _(ctx):
    return [gxe.ExpectTableColumnsToMatchSet(column_set=SPOTIFY_REQUIRED, exact_match=False,
                                             meta=_m(_R("DQ-S02")))]


@rule(rule_id="DQ-S03", layer="spotify_raw", attributes="popularity", dimension="Validity",
      description="popularity es obligatoria y está en [0, 100].",
      threshold="100% dentro de rango y sin nulos", severity=CRITICAL, requirements="AR-1, AR-3",
      justification="Es la medida principal; fuera de rango invalida los promedios. Perfilado: min 0, max 100.")
def _(ctx):
    m = _m(_R("DQ-S03"))
    return [gxe.ExpectColumnValuesToNotBeNull(column="popularity", mostly=1.0, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="popularity", min_value=0, max_value=100, mostly=1.0, meta=m)]


@rule(rule_id="DQ-S04", layer="spotify_raw", attributes="danceability, energy, valence", dimension="Validity",
      description="Las características de audio acotadas deben estar en [0, 1].",
      threshold="100% dentro de [0,1]", severity=CRITICAL, requirements="AR-1",
      justification="Definición de la API de Spotify (rango [0,1]). Un valor fuera de rango delata corrupción.")
def _(ctx):
    m = _m(_R("DQ-S04"))
    return [gxe.ExpectColumnValuesToBeBetween(column=c, min_value=0, max_value=1, mostly=1.0, meta=m)
            for c in ("danceability", "energy", "valence")]


@rule(rule_id="DQ-S05", layer="spotify_raw", attributes="track_id + track_genre", dimension="Uniqueness",
      description="El par (track_id, track_genre) debe ser único (es el grano de la fuente).",
      threshold="≥ 98% de filas fuera de grupos duplicados (observado 99.22%)", severity=WARNING, requirements="AR-2",
      justification="Perfilado: 450 pares repetidos; GX marca las 2 filas de cada par (900 filas = 0.78%). track_id repetido "
                    "SÍ es esperado (varios géneros), pero el par repetido no. El umbral (2%, ~2.5x lo observado) "
                    "alerta si la duplicación se vuelve sistemática. Se deduplica en transform (T-03).")
def _(ctx):
    return [gxe.ExpectCompoundColumnsToBeUnique(column_list=["track_id", "track_genre"], mostly=0.98,
                                                meta=_m(_R("DQ-S05")))]


@rule(rule_id="DQ-S06", layer="spotify_raw", attributes="tempo, time_signature", dimension="Validity",
      description="tempo > 0 y time_signature entre 1 y 7 (0 significa 'no detectado').",
      threshold="≥ 99.5% válidos (observado: 99.86% tempo, 99.86% time_signature)", severity=WARNING,
      requirements="AR-1", justification="Perfilado: 157 tempo=0 y 163 time_signature=0 (valores imposibles/centinela). "
                                          "No bloquean: se convierten a NULL en transform.")
def _(ctx):
    m = _m(_R("DQ-S06"))
    return [gxe.ExpectColumnValuesToBeBetween(column="tempo", min_value=0, strict_min=True, mostly=0.995, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="time_signature", min_value=1, max_value=7, mostly=0.995, meta=m)]


@rule(rule_id="DQ-S07", layer="spotify_raw", attributes="artists, track_name", dimension="Completeness",
      description="artists y track_name deben estar presentes (claves de integración con Grammy).",
      threshold="≥ 99.9% no nulos (observado 99.999%)", severity=WARNING, requirements="AR-1, AR-2, AR-3",
      justification="Perfilado: 1 fila sin artists/track_name. Sin ellos no se puede integrar; se pone en cuarentena.")
def _(ctx):
    m = _m(_R("DQ-S07"))
    return [gxe.ExpectColumnValuesToNotBeNull(column=c, mostly=0.999, meta=m) for c in ("artists", "track_name")]


@rule(rule_id="DQ-S08", layer="spotify_raw", attributes="(tabla)", dimension="Completeness/Volume",
      description="El lote debe tener un volumen mínimo razonable de filas.",
      threshold="50,000 ≤ filas ≤ 500,000 (observado 114,000)", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Un lote truncado (<50% del volumen histórico) sesgaría todos los KPIs.")
def _(ctx):
    return [gxe.ExpectTableRowCountToBeBetween(min_value=50_000, max_value=500_000, meta=_m(_R("DQ-S08")))]


@rule(rule_id="DQ-S09", layer="spotify_raw", attributes="track_id", dimension="Validity",
      description="track_id debe tener 22 caracteres (formato ID de Spotify).",
      threshold="100% longitud 22", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Perfilado: 100% longitud 22. Protege el tipo CHAR(22) de dim_track.")
def _(ctx):
    return [gxe.ExpectColumnValueLengthsToEqual(column="track_id", value=22, mostly=1.0, meta=_m(_R("DQ-S09")))]


@rule(rule_id="DQ-S10", layer="spotify_raw", attributes="track_genre", dimension="Consistency",
      description="Monitoreo: número de géneros distintos dentro del rango histórico.",
      threshold="100 ≤ géneros distintos ≤ 150 (observado 114)", severity=INFO, requirements="AR-2",
      justification="Señal de tendencia: cambios fuertes sugieren cambio de catálogo/taxonomía.")
def _(ctx):
    return [gxe.ExpectColumnUniqueValueCountToBeBetween(column="track_genre", min_value=100, max_value=150,
                                                        meta=_m(_R("DQ-S10")))]


# ============================ GRAMMY · RAW ============================
@rule(rule_id="DQ-G01", layer="grammys_raw", attributes="10 columnas requeridas", dimension="Structure/Validity",
      description="La tabla fuente debe contener las columnas del contrato.",
      threshold="Todas presentes", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Contrato de la fuente relacional. Columna faltante = falla determinista.")
def _(ctx):
    return [gxe.ExpectTableColumnsToMatchSet(column_set=GRAMMY_REQUIRED, exact_match=False,
                                             meta=_m(_R("DQ-G01")))]


@rule(rule_id="DQ-G02", layer="grammys_raw", attributes="year", dimension="Validity/Timeliness",
      description="year obligatorio y entre 1958 (1.er Grammy) y 2030.",
      threshold="100% en [1958, 2030]", severity=CRITICAL, requirements="AR-3",
      justification="AR-3 agrupa por década del primer Grammy; un año imposible corrompe la dimensión. "
                    "Perfilado: rango observado 1958–2019. Se usa en la Prueba B (año=1800).")
def _(ctx):
    m = _m(_R("DQ-G02"))
    return [gxe.ExpectColumnValuesToNotBeNull(column="year", mostly=1.0, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="year", min_value=1958, max_value=2030, mostly=1.0, meta=m)]


@rule(rule_id="DQ-G03", layer="grammys_raw", attributes="category", dimension="Completeness",
      description="Toda nominación debe tener categoría.",
      threshold="100% no nulos", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="La categoría define qué se premió; sin ella la fila no es interpretable. Perfilado: 0 nulos.")
def _(ctx):
    return [gxe.ExpectColumnValuesToNotBeNull(column="category", mostly=1.0, meta=_m(_R("DQ-G03")))]


@rule(rule_id="DQ-G04", layer="grammys_raw", attributes="nominee", dimension="Completeness",
      description="nominee presente (clave para vincular a nivel de canción).",
      threshold="≥ 99% no nulos (observado 99.88%)", severity=WARNING, requirements="AR-1",
      justification="Perfilado: 6 nulos (Remixer of the Year, Best New Country…). Afectan solo el vínculo por canción.")
def _(ctx):
    return [gxe.ExpectColumnValuesToNotBeNull(column="nominee", mostly=0.99, meta=_m(_R("DQ-G04")))]


@rule(rule_id="DQ-G05", layer="grammys_raw", attributes="artist", dimension="Completeness",
      description="Proporción de nominaciones con artista identificado.",
      threshold="≥ 55% no nulos (observado 61.7%)", severity=WARNING, requirements="AR-1, AR-2, AR-3",
      justification="Perfilado: 38% nulo, concentrado en categorías cuyo crédito está en 'workers' "
                    "(Song Of The Year, Opera, Album Notes…). Es una limitación conocida; el umbral deja ~7 pp de "
                    "margen y alerta si la cobertura de integración empeora.")
def _(ctx):
    return [gxe.ExpectColumnValuesToNotBeNull(column="artist", mostly=0.55, meta=_m(_R("DQ-G05")))]


@rule(rule_id="DQ-G06", layer="grammys_raw", attributes="year+category+nominee+artist", dimension="Uniqueness",
      description="No debe haber nominaciones duplicadas en el grano de la fuente.",
      threshold="≥ 99.9% únicas (observado 100%)", severity=WARNING, requirements="AR-1, AR-2, AR-3",
      justification="Duplicados inflarían conteos de nominaciones por artista (KPI-3).")
def _(ctx):
    return [gxe.ExpectCompoundColumnsToBeUnique(column_list=["year", "category", "nominee", "artist"],
                                                mostly=0.999, meta=_m(_R("DQ-G06")))]


@rule(rule_id="DQ-G07", layer="grammys_raw", attributes="winner", dimension="Validity/Consistency",
      description="winner debería contener ambos valores (True y False) si distingue ganadores de nominados.",
      threshold="Valores distintos ⊇ {True, False} (observado: solo True)", severity=WARNING,
      requirements="AR-1",
      justification="Hallazgo de perfilado: winner=True en el 100% de las filas. El dataset solo permite hablar de "
                    "'vinculado a Grammy', NO de 'ganador vs. no ganador'. Esta regla FALLA a propósito como "
                    "Warning documentado: se registra y el pipeline continúa (el análisis no usa winner como "
                    "discriminante).")
def _(ctx):
    return [gxe.ExpectColumnDistinctValuesToContainSet(column="winner", value_set=[True, False],
                                                       meta=_m(_R("DQ-G07")))]


@rule(rule_id="DQ-G08", layer="grammys_raw", attributes="(tabla)", dimension="Completeness/Volume",
      description="Volumen mínimo y máximo de filas del lote Grammy.",
      threshold="1,000 ≤ filas ≤ 20,000 (observado 4,810)", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Una tabla fuente vacía/truncada produciría vínculos Grammy = 0.")
def _(ctx):
    return [gxe.ExpectTableRowCountToBeBetween(min_value=1_000, max_value=20_000, meta=_m(_R("DQ-G08")))]


@rule(rule_id="DQ-G09", layer="grammys_raw", attributes="category", dimension="Consistency",
      description="Monitoreo: número de categorías distintas (hay variaciones de mayúsculas/ortografía).",
      threshold="400 ≤ categorías ≤ 900 (observado 638)", severity=INFO, requirements="AR-3",
      justification="Señal de tendencia sobre la dispersión de etiquetas de categoría.")
def _(ctx):
    return [gxe.ExpectColumnUniqueValueCountToBeBetween(column="category", min_value=400, max_value=900,
                                                        meta=_m(_R("DQ-G09")))]


# ============================ PREPARED ============================
@rule(rule_id="DQ-P01", layer="prepared", attributes="esquema preparado", dimension="Structure",
      description="El dataset preparado tiene exactamente las columnas esperadas por el modelo dimensional.",
      threshold="Conjunto de columnas idéntico", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Invariante post-transformación: load_dw depende de este contrato.")
def _(ctx):
    return [gxe.ExpectTableColumnsToMatchSet(column_set=PREPARED_COLUMNS, exact_match=True, meta=_m(_R("DQ-P01")))]


@rule(rule_id="DQ-P02", layer="prepared", attributes="track_id, track_genre, primary_artist_norm",
      dimension="Completeness", description="Llaves del modelo dimensional sin nulos.",
      threshold="100% no nulos", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Columnas NOT NULL en dim_track / dim_genre / dim_artist.")
def _(ctx):
    m = _m(_R("DQ-P02"))
    return [gxe.ExpectColumnValuesToNotBeNull(column=c, mostly=1.0, meta=m)
            for c in ("track_id", "track_genre", "primary_artist_norm")]


@rule(rule_id="DQ-P03", layer="prepared", attributes="track_id + track_genre", dimension="Uniqueness",
      description="El grano del hecho se cumple: una fila por (track_id, track_genre).",
      threshold="100% únicas", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Garantiza UNIQUE(track_key, genre_key) del hecho y detecta multiplicación de filas "
                    "por joins ambiguos (duplicate-match).")
def _(ctx):
    return [gxe.ExpectCompoundColumnsToBeUnique(column_list=["track_id", "track_genre"], mostly=1.0,
                                                meta=_m(_R("DQ-P03")))]


@rule(rule_id="DQ-P04", layer="prepared", attributes="recognition_level", dimension="Validity",
      description="recognition_level pertenece al dominio permitido (3 niveles).",
      threshold="100% en el dominio", severity=CRITICAL, requirements="AR-1, AR-2",
      justification="Es la FK a dim_recognition; un valor fuera de dominio rompe la integridad referencial.")
def _(ctx):
    return [gxe.ExpectColumnValuesToBeInSet(column="recognition_level", value_set=RECOGNITION_LEVELS, mostly=1.0,
                                            meta=_m(_R("DQ-P04")))]


@rule(rule_id="DQ-P05", layer="prepared", attributes="popularity", dimension="Validity",
      description="popularity no nula y en [0, 100] tras la transformación.",
      threshold="100%", severity=CRITICAL, requirements="AR-1, AR-3",
      justification="CHECK (popularity BETWEEN 0 AND 100) en fact_track_listing.")
def _(ctx):
    m = _m(_R("DQ-P05"))
    return [gxe.ExpectColumnValuesToNotBeNull(column="popularity", mostly=1.0, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="popularity", min_value=0, max_value=100, mostly=1.0, meta=m)]


@rule(rule_id="DQ-P06", layer="prepared", attributes="tempo, time_signature, duration_ms", dimension="Validity",
      description="Tras convertir centinelas a NULL, los valores presentes son físicamente válidos.",
      threshold="100% de los no nulos en rango (tempo 30–260; time_sig 1–7; duración > 0)", severity=CRITICAL,
      requirements="AR-1",
      justification="Invariante post-transformación de la regla de limpieza T-02 (ceros -> NULL). "
                    "Rango de tempo basado en perfilado (min no cero 30.2, max 243.4).")
def _(ctx):
    m = _m(_R("DQ-P06"))
    return [gxe.ExpectColumnValuesToBeBetween(column="tempo", min_value=30, max_value=260, mostly=1.0, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="time_signature", min_value=1, max_value=7, mostly=1.0, meta=m),
            gxe.ExpectColumnValuesToBeBetween(column="duration_ms", min_value=1, mostly=1.0, meta=m)]


@rule(rule_id="DQ-P07", layer="prepared", attributes="(tabla)", dimension="Consistency/Integrity",
      description="Reconciliación: filas preparadas = filas Spotify limpias (los joins no agregan ni pierden filas).",
      threshold="Igualdad exacta con el conteo esperado (reconciliation.json)", severity=CRITICAL,
      requirements="AR-1, AR-2, AR-3",
      justification="Integración many-to-one: cualquier diferencia indica fan-out (duplicate matches) o pérdida.")
def _(ctx):
    return [gxe.ExpectTableRowCountToEqual(value=int(ctx["expected_rows"]), meta=_m(_R("DQ-P07")))]


@rule(rule_id="DQ-P08", layer="prepared", attributes="grammy_artist_linked, grammy_track_linked",
      dimension="Consistency", description="Invariante: una pista vinculada por canción también está vinculada por artista.",
      threshold="artist_linked ≥ track_linked en 100% de filas", severity=CRITICAL, requirements="AR-1, AR-2",
      justification="Por construcción del contrato de integración (el vínculo de canción exige artista coincidente).")
def _(ctx):
    return [gxe.ExpectColumnPairValuesAToBeGreaterThanB(column_A="grammy_artist_linked",
                                                        column_B="grammy_track_linked", or_equal=True,
                                                        meta=_m(_R("DQ-P08")))]


@rule(rule_id="DQ-P09", layer="prepared", attributes="grammy_artist_linked", dimension="Completeness/Readiness",
      description="Preparación analítica: suficientes filas vinculadas a Grammy para comparar grupos.",
      threshold="≥ 1,000 filas vinculadas por artista", severity=CRITICAL, requirements="AR-1, AR-2, AR-3",
      justification="Si la integración no vincula casi nada, los KPIs comparativos no tienen sentido "
                    "(umbral >> 30, mínimo estadístico por grupo).")
def _(ctx):
    return [gxe.ExpectColumnSumToBeBetween(column="grammy_artist_linked", min_value=1_000,
                                           meta=_m(_R("DQ-P09")))]


@rule(rule_id="DQ-P10", layer="prepared", attributes="grammy_track_linked", dimension="Completeness/Readiness",
      description="Cobertura del vínculo por canción (muestra mínima).",
      threshold="≥ 100 filas vinculadas por canción", severity=WARNING, requirements="AR-1",
      justification="Con pocas canciones vinculadas el nivel 'Track Grammy-linked' pierde significancia; "
                    "es una advertencia, no bloquea porque AR-2/AR-3 usan vínculo por artista.")
def _(ctx):
    return [gxe.ExpectColumnSumToBeBetween(column="grammy_track_linked", min_value=100, meta=_m(_R("DQ-P10")))]


@rule(rule_id="DQ-P11", layer="prepared", attributes="grammy_artist_linked", dimension="Consistency",
      description="Monitoreo: % de filas vinculadas a Grammy dentro de un rango plausible.",
      threshold="1% ≤ % vinculado ≤ 60%", severity=INFO, requirements="AR-2",
      justification="Señal de tendencia de la calidad del matching (muy alto = falsos positivos; muy bajo = normalización rota).")
def _(ctx):
    return [gxe.ExpectColumnMeanToBeBetween(column="grammy_artist_linked", min_value=0.01, max_value=0.60,
                                            meta=_m(_R("DQ-P11")))]


def rules_for(layer: str):
    return [r for r in RULES if r.layer == layer]
