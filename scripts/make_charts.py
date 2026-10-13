"""Genera las 3 visualizaciones (PNG) consultando las VISTAS del Data Warehouse (no los CSV).
Sirve como evidencia reproducible y como respaldo del dashboard de BI.
Uso: python scripts/make_charts.py     -> docs/evidence/dashboard/*.png"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):      # consola de Windows (cp1252): imprimir tildes sin error
    sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

from src import config

OUT = config.EVIDENCE / "dashboard"
OUT.mkdir(parents=True, exist_ok=True)
eng = create_engine(config.db_url(config.DW_DB))
q = lambda sql: pd.read_sql(sql, eng)

# KPI-1 · AR-1
d = q("SELECT * FROM vw_kpi_popularity_by_recognition")
fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.bar(d.recognition_level, d.avg_popularity, color=["#9aa5b1", "#3b82f6", "#16a34a"])
ax.bar_label(bars, fmt="%.1f")
ax.set_ylabel("Popularidad promedio (0-100)")
ax.set_title("KPI-1 (AR-1) · Popularidad Spotify según vínculo con los Grammy")
for i, n in enumerate(d.listings):
    ax.text(i, 1, f"n={n:,}", ha="center", color="white", fontsize=9)
fig.tight_layout(); fig.savefig(OUT / "kpi1_popularity_by_recognition.png", dpi=150); plt.close(fig)

# KPI-2 · AR-2
d = q("SELECT genre_name, grammy_share_pct, listings FROM vw_kpi_genre_grammy_share "
      "ORDER BY grammy_share_pct DESC LIMIT 15").iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(d.genre_name, d.grammy_share_pct, color="#3b82f6")
ax.set_xlabel("% de listados vinculados a Grammy")
ax.set_title("KPI-2 (AR-2) · Top 15 géneros por proporción vinculada a Grammy")
fig.tight_layout(); fig.savefig(OUT / "kpi2_genre_grammy_share.png", dpi=150); plt.close(fig)

# KPI-3 · AR-3
d = q("SELECT first_grammy_decade, artists, avg_popularity FROM vw_kpi_popularity_by_grammy_decade")
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(d.first_grammy_decade, d.avg_popularity, marker="o", color="#16a34a")
for x, y, n in zip(d.first_grammy_decade, d.avg_popularity, d.artists):
    ax.annotate(f"{y:.1f}\n({n} art.)", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
ax.set_ylabel("Popularidad promedio"); ax.set_xlabel("Década del primer Grammy del artista")
ax.set_title("KPI-3 (AR-3) · Popularidad según la época del primer Grammy"); ax.margins(y=0.2)
fig.tight_layout(); fig.savefig(OUT / "kpi3_popularity_by_grammy_decade.png", dpi=150); plt.close(fig)
print("Gráficos generados en", OUT)
print(q("SELECT * FROM vw_kpi_summary").T.to_string())
