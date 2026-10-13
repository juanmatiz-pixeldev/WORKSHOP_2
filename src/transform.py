"""TRANSFORMACIÓN + INTEGRACIÓN (una sola fase; ver docs/transformation_decisions.md).

Reglas de ingeniería (cada una con su justificación en docs/transformation_decisions.md):
  T-01 Quitar columna índice 'Unnamed: 0' (artefacto de exportación, sin valor analítico)
  T-02 Centinelas imposibles -> NULL (tempo<=0, time_signature<=0, duration_ms<=0). NO se borran filas.
  T-03 Deduplicar el grano (track_id, track_genre) conservando la mayor popularidad
  T-04 Filas sin artists/track_name -> CUARENTENA (no se pueden integrar)
  T-05 Separar 'artists' (';') -> primary_artist = primer artista acreditado
  T-06 Normalizar nombres (acentos, mayúsculas, puntuación, 'the ') -> llaves de matching
  T-07 Grammy: dividir 'artist' compuesto (&, and, featuring, with, ',' ...) en tokens
  T-08 Integración Spotify <-> Grammy (ver contrato) y derivación de recognition_level
"""
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd

from . import config
from .errors import IntegrationError

log = logging.getLogger("airflow.task")

_SPLIT = re.compile(r"\s*(?:,|&|/|\band\b|\bfeaturing\b|\bfeat\.?|\bwith\b)\s*", flags=re.I)


def norm(value) -> str | None:
    """Normaliza un nombre para usarlo como llave de matching (idempotente)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = unicodedata.normalize("NFKC", s).casefold().replace("&", " and ")
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^\w ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    return s or None


def title_key(value) -> str | None:
    """Llave de título: quita '(feat. X)', '[Remastered]' y sufijos ' - Remastered'."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    s = re.sub(r"\s*[\(\[].*?[\)\]]", "", str(value)).split(" - ")[0]
    return norm(s) or norm(value)


def grammy_tokens(artist, spotify_primary: set) -> list[str]:
    """Tokens de matching de un crédito Grammy. Si el crédito COMPLETO ya coincide con un artista
    de Spotify (p. ej. 'Earth, Wind & Fire') se usa entero; si no, se usan sus partes."""
    if artist is None or pd.isna(artist):
        return []
    full = norm(artist)
    if full in spotify_primary:
        return [full]
    parts = [norm(p) for p in _SPLIT.split(str(artist))]
    return sorted({p for p in parts if p and len(p) >= 3})


def transform_and_integrate(spotify_meta: dict, grammys_meta: dict, batch_id: str) -> dict:
    sp = pd.read_parquet(spotify_meta["path"])
    gr = pd.read_parquet(grammys_meta["path"])
    rec = {"batch_id": batch_id, "created_at": datetime.now(timezone.utc).isoformat(),
           "spotify_rows_in": int(len(sp)), "grammy_rows_in": int(len(gr))}
    log.info("[batch=%s] transform: spotify=%d filas, grammy=%d filas", batch_id, len(sp), len(gr))

    # ---------------- SPOTIFY ----------------
    sp = sp.drop(columns=[c for c in sp.columns if c.startswith("Unnamed")])                      # T-01
    for c in ("artists", "album_name", "track_name", "track_genre", "track_id"):
        sp[c] = sp[c].astype("string").str.strip()
    bad = sp[["track_id", "artists", "track_name", "popularity"]].isna().any(axis=1)             # T-04
    quarantine = sp[bad]
    quarantine.to_parquet(config.batch_dir(batch_id) / "spotify_quarantine.parquet", index=False)
    sp = sp[~bad].copy()
    rec["spotify_quarantined_missing_keys"] = int(bad.sum())

    for col, bad_mask in (("tempo", sp["tempo"] <= 0), ("time_signature", sp["time_signature"] <= 0),
                          ("duration_ms", sp["duration_ms"] <= 0)):                              # T-02
        rec[f"spotify_{col}_sentinel_to_null"] = int(bad_mask.sum())
        sp[col] = sp[col].mask(bad_mask)
    sp["time_signature"] = sp["time_signature"].astype("Int64")
    sp["duration_ms"] = sp["duration_ms"].astype("Int64")

    sp["track_genre"] = sp["track_genre"].str.lower()
    before = len(sp)                                                                             # T-03
    sp = (sp.sort_values("popularity", ascending=False, kind="stable")
            .drop_duplicates(["track_id", "track_genre"], keep="first")
            .sort_values(["track_id", "track_genre"]).reset_index(drop=True))
    rec["spotify_duplicates_removed"] = int(before - len(sp))

    sp["artists_raw"] = sp["artists"]                                                            # T-05
    sp["primary_artist"] = sp["artists"].str.split(";").str[0].str.strip()
    sp["n_artists"] = sp["artists"].str.count(";").add(1).astype("int16")
    sp["primary_artist_norm"] = sp["primary_artist"].map(norm)                                   # T-06
    sp["track_key_norm"] = sp["track_name"].map(title_key)
    rec["spotify_rows_out"] = int(len(sp))
    sp_primary = set(sp["primary_artist_norm"].dropna())

    # ---------------- GRAMMY ----------------
    gr = gr.copy()
    for c in ("category", "nominee", "artist", "workers"):
        gr[c] = gr[c].astype("string").str.strip().replace("", pd.NA)
    gr["nomination_id"] = range(len(gr))
    gr["nominee_key"] = gr["nominee"].map(title_key)
    gr["tokens"] = gr["artist"].map(lambda a: grammy_tokens(a, sp_primary))                      # T-07
    tok = gr[["nomination_id", "nominee_key", "year", "winner", "tokens"]].explode("tokens")
    tok = tok.rename(columns={"tokens": "token"}).dropna(subset=["token"]).drop_duplicates(["nomination_id", "token"])

    # ---------------- INTEGRACIÓN (contrato) ----------------
    # Nivel artista: 1 fila por token Grammy  -> join MANY(Spotify) : ONE(token)
    art = (tok.groupby("token").agg(artist_grammy_nominations=("nomination_id", "nunique"),
                                    artist_grammy_wins=("winner", "sum"),
                                    artist_first_grammy_year=("year", "min")).reset_index())
    # Nivel canción: 1 fila por (token, título) -> evita fan-out si una canción ganó en varias categorías
    trk = (tok.dropna(subset=["nominee_key"]).groupby(["token", "nominee_key"])
              .agg(track_grammy_nominations=("nomination_id", "nunique")).reset_index())

    n0 = len(sp)
    out = sp.merge(art, how="left", left_on="primary_artist_norm", right_on="token", validate="many_to_one")
    out = out.drop(columns="token")
    out = out.merge(trk, how="left", left_on=["primary_artist_norm", "track_key_norm"],
                    right_on=["token", "nominee_key"], validate="many_to_one").drop(columns=["token", "nominee_key"])
    if len(out) != n0:
        raise IntegrationError(f"El join cambió el número de filas: {n0} -> {len(out)} (fan-out)")

    out["grammy_artist_linked"] = out["artist_grammy_nominations"].notna().astype("int8")        # T-08
    out["grammy_track_linked"] = out["track_grammy_nominations"].notna().astype("int8")
    for c in ("artist_grammy_nominations", "artist_grammy_wins", "track_grammy_nominations"):
        out[c] = out[c].fillna(0).astype("int32")
    out["artist_first_grammy_year"] = out["artist_first_grammy_year"].astype("Int64")
    out["artist_first_grammy_decade"] = (
        ((out["artist_first_grammy_year"] // 10) * 10).astype("Int64").astype("string") + "s")
    out["recognition_level"] = "No Grammy link"
    out.loc[out["grammy_artist_linked"] == 1, "recognition_level"] = "Artist Grammy-linked"
    out.loc[out["grammy_track_linked"] == 1, "recognition_level"] = "Track Grammy-linked"

    from .rules import PREPARED_COLUMNS
    prepared = out[PREPARED_COLUMNS].copy()
    path = config.batch_dir(batch_id) / "prepared_integrated.parquet"
    prepared.to_parquet(path, index=False)

    # ---------------- RECONCILIACIÓN ----------------
    all_tok = set(tok["token"])
    nom_with_tokens = gr["tokens"].map(len).gt(0)
    matched_noms = tok[tok["token"].isin(sp_primary)]["nomination_id"].nunique()
    rec.update({
        "grammy_nominations_total": int(len(gr)),
        "grammy_nominations_without_artist": int(gr["artist"].isna().sum()),
        "grammy_nominations_with_artist": int(nom_with_tokens.sum()),
        "grammy_nominations_matched_to_spotify_artist": int(matched_noms),
        "grammy_nominations_unmatched_with_artist": int(nom_with_tokens.sum() - matched_noms),
        "grammy_artist_match_rate_pct": round(100 * matched_noms / max(int(nom_with_tokens.sum()), 1), 2),
        "grammy_distinct_tokens": len(all_tok),
        "spotify_listings_artist_linked": int(prepared["grammy_artist_linked"].sum()),
        "spotify_listings_track_linked": int(prepared["grammy_track_linked"].sum()),
        "spotify_listing_artist_linked_pct": round(100 * prepared["grammy_artist_linked"].mean(), 2),
        "prepared_rows": int(len(prepared)), "expected_prepared_rows": int(rec["spotify_rows_out"]),
        "rows_preserved_by_joins": bool(len(prepared) == rec["spotify_rows_out"]),
        "prepared_path": str(path),
    })
    rpath = config.evidence_dir(batch_id) / "reconciliation.json"
    rpath.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    log.info("[batch=%s] transform OK: spotify %d->%d (dups=%d, cuarentena=%d) | grammy match artista=%s%% | "
             "listings vinculados artista=%d, canción=%d | reconciliación=%s",
             batch_id, rec["spotify_rows_in"], rec["spotify_rows_out"], rec["spotify_duplicates_removed"],
             rec["spotify_quarantined_missing_keys"], rec["grammy_artist_match_rate_pct"],
             rec["spotify_listings_artist_linked"], rec["spotify_listings_track_linked"], rpath)
    return {"prepared_path": str(path), "reconciliation_path": str(rpath), "rows": int(len(prepared)),
            "expected_rows": rec["expected_prepared_rows"], "batch_id": batch_id}
