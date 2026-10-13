"""Genera docs/quality_rules.md y docs/gx_expectation_map.md DESDE src/rules.py (fuente única de verdad),
así la documentación nunca diverge del código.   Uso: python scripts/export_quality_docs.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import rules

DOCS = Path(__file__).resolve().parents[1] / "docs"
LAYER = {"spotify_raw": "Spotify · raw", "grammys_raw": "Grammy · raw", "prepared": "Prepared"}
esc = lambda s: str(s).replace("|", "\\|")

lines = ["# Reglas de calidad de datos (generado desde `src/rules.py`)\n",
         "Severidad: **Critical** bloquea el camino downstream · **Warning** se registra y continúa · "
         "**Informational** solo monitoreo. Detalle de la política en [failure_policy.md](failure_policy.md).\n",
         "| Rule ID | Dataset / Layer | Atributo(s) | Dimensión | Regla | Métrica / Umbral | Severidad | Requisito | Justificación |",
         "|---|---|---|---|---|---|---|---|---|"]
for r in rules.RULES:
    lines.append(f"| {r.rule_id} | {LAYER[r.layer]} | {esc(r.attributes)} | {r.dimension} | {esc(r.description)} | "
                 f"{esc(r.threshold)} | {r.severity} | {r.requirements} | {esc(r.justification)} |")
(DOCS / "quality_rules.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

m = ["# Mapeo Rule ID → Great Expectations\n",
     "Cada Expectation lleva `meta={rule_id, severity}`. Suites: `spotify_raw_suite`, `grammys_raw_suite`, "
     "`prepared_suite` (en `gx/expectations/`). Validation Definitions: `<capa>_validation`. "
     "Checkpoints: `<capa>_checkpoint`.\n",
     "| Rule ID | Suite | Expectation GX | Parámetros clave | Severidad |", "|---|---|---|---|---|"]
for r in rules.RULES:
    for e in r.build({"expected_rows": 0}):
        kw = {k: v for k, v in e.configuration.kwargs.items() if k not in ("batch_id",)}
        short = ", ".join(f"{k}={v}" for k, v in kw.items())
        m.append(f"| {r.rule_id} | {r.layer}_suite | `{e.expectation_type}` | {esc(short[:160])} | {r.severity} |")
(DOCS / "gx_expectation_map.md").write_text("\n".join(m) + "\n", encoding="utf-8")
print(f"{len(rules.RULES)} reglas exportadas a docs/quality_rules.md y docs/gx_expectation_map.md")
