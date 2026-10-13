"""VALIDACIÓN con Great Expectations (GX Core 1.x) + aplicación de la POLÍTICA por severidad.

Jerarquía GX usada (documentada en README):
  Data Source (pandas) -> Data Asset (dataframe) -> Batch Definition (whole dataframe)
  Expectation Suite  : conjunto de Expectations de UNA capa (spotify_raw / grammys_raw / prepared)
  Validation Definition : asocia Batch Definition + Suite
  Checkpoint         : ejecuta la Validation Definition y guarda el resultado
Cada Expectation lleva meta={rule_id, severity} -> trazabilidad regla <-> expectation.

Política (docs/failure_policy.md):
  Critical      -> DataQualityError (la tarea falla, el downstream NO corre)
  Warning       -> se registra (WARNING en el log + JSON) y el pipeline continúa
  Informational -> se registra para monitoreo
La validación NO modifica los datos.
"""
import json
import logging
from datetime import datetime, timezone

import great_expectations as gx
import pandas as pd

from . import config, rules
from .errors import DataQualityError

log = logging.getLogger("airflow.task")

LAYERS = {"spotify_raw": "Spotify CSV (raw)", "grammys_raw": "Grammy PostgreSQL (raw)",
          "prepared": "Dataset preparado/integrado"}


def _get_or_add(getter, adder):
    try:
        return getter()
    except Exception:
        return adder()


def _build_gx_objects(context, layer: str, ctx: dict):
    ds = context.data_sources.add_or_update_pandas(name="pipeline_pandas")
    asset = _get_or_add(lambda: ds.get_asset(f"{layer}_asset"), lambda: ds.add_dataframe_asset(name=f"{layer}_asset"))
    bdef = _get_or_add(lambda: asset.get_batch_definition(f"{layer}_whole_df"),
                       lambda: asset.add_batch_definition_whole_dataframe(f"{layer}_whole_df"))
    expectations = [e for r in rules.rules_for(layer) for e in r.build(ctx)]
    suite = context.suites.add_or_update(gx.ExpectationSuite(name=f"{layer}_suite", expectations=expectations))
    vdef = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(name=f"{layer}_validation", data=bdef, suite=suite))
    checkpoint = context.checkpoints.add_or_update(
        gx.Checkpoint(name=f"{layer}_checkpoint", validation_definitions=[vdef],
                      result_format={"result_format": "SUMMARY"}))
    return checkpoint, len(expectations)


def run_gate(layer: str, df: pd.DataFrame, batch_id: str, ctx: dict | None = None) -> dict:
    """Ejecuta el gate de `layer`. Devuelve el resumen; lanza DataQualityError si falla una regla Critical."""
    ctx = ctx or {}
    context = gx.get_context(mode="file", project_root_dir=str(config.ROOT))
    checkpoint, n_exp = _build_gx_objects(context, layer, ctx)
    log.info("[batch=%s] GX gate '%s': %d filas, %d expectations", batch_id, layer, len(df), n_exp)
    cp_result = checkpoint.run(batch_parameters={"dataframe": df})

    rule_index = {r.rule_id: r for r in rules.RULES}
    items = []
    for vr in cp_result.run_results.values():
        for er in vr.results:
            meta = er.expectation_config.meta or {}
            res = er.result or {}
            items.append({
                "rule_id": meta.get("rule_id"), "severity": meta.get("severity"),
                "expectation": er.expectation_config.type,
                "kwargs": {k: v for k, v in er.expectation_config.kwargs.items() if k != "batch_id"},
                "success": bool(er.success),
                "observed_value": res.get("observed_value"),
                "element_count": res.get("element_count"),
                "unexpected_count": res.get("unexpected_count"),
                "unexpected_percent": res.get("unexpected_percent"),
            })

    def failed(sev):
        return sorted({i["rule_id"] for i in items if i["severity"] == sev and not i["success"]})

    critical, warning, info = failed(rules.CRITICAL), failed(rules.WARNING), failed(rules.INFO)
    summary = {
        "batch_id": batch_id, "layer": layer, "dataset": LAYERS[layer], "rows_validated": int(len(df)),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "gx": {"suite": f"{layer}_suite", "validation_definition": f"{layer}_validation",
               "checkpoint": f"{layer}_checkpoint", "gx_overall_success": bool(cp_result.success)},
        "policy_outcome": "FAIL" if critical else ("PASS_WITH_WARNINGS" if warning else "PASS"),
        "n_expectations": len(items), "failed_critical": critical, "failed_warning": warning,
        "failed_informational": info, "results": items,
    }
    out = config.evidence_dir(batch_id) / f"validation_{layer}.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    for rid in warning:   # visibilidad de Warnings
        log.warning("[batch=%s] %s WARNING %s: %s | umbral: %s", batch_id, layer, rid,
                    rule_index[rid].description, rule_index[rid].threshold)
    for rid in info:
        log.info("[batch=%s] %s INFO %s no cumple (solo monitoreo): %s", batch_id, layer, rid,
                 rule_index[rid].description)
    log.info("[batch=%s] gate '%s' resultado=%s | críticas=%s warnings=%s info=%s | evidencia=%s",
             batch_id, layer, summary["policy_outcome"], critical, warning, info, out)
    if critical:
        detail = "; ".join(f"{rid} ({rule_index[rid].description} Umbral: {rule_index[rid].threshold})"
                           for rid in critical)
        raise DataQualityError(f"Gate '{layer}' BLOQUEADO por regla(s) CRITICAL: {detail}. "
                               f"Ver {out}")
    return summary
