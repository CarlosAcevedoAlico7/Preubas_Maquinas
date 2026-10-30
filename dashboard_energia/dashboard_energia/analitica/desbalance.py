"""Sección 5.6 del notebook: desbalance antes/después del filtro activo."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import FASES_FP, FASES_I, FASES_KW, H_INTERVALO, Parametros

ORDEN = ["Antes", "Transición", "Después"]


def intervalos_produccion(limpio: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    """Intervalos en producción etiquetados con el período respecto al filtro."""
    op = limpio[limpio["kW_Total"] >= p.umbral_produccion_kw].copy()
    op["periodo"] = np.select(
        [op.index < pd.Timestamp(p.fecha_filtro), op.index >= pd.Timestamp(p.fin_transicion)],
        ["Antes", "Después"], default="Transición")
    return op


def tabla_periodos(op: pd.DataFrame) -> pd.DataFrame:
    t = (op.groupby("periodo")
           .agg(desde=("kW_Total", lambda s: s.index.min()),
                hasta=("kW_Total", lambda s: s.index.max()),
                intervalos=("kW_Total", "size"))
           .reindex(ORDEN))
    t["horas_en_produccion"] = t["intervalos"] * H_INTERVALO
    return t


def desbalance_diario(op: pd.DataFrame) -> pd.DataFrame:
    """5.6.1: mediana diaria (días con ≥ 6 h en producción) y media móvil de 15 días."""
    cols = ["Desbalance_I_pct", "Desbalance_kW_pct", "Desbalance_V_pct", "kW_Total"]
    d = op[cols].resample("D").median()
    n = op["kW_Total"].resample("D").size()
    d[n < 24] = np.nan
    for c in cols[:3]:
        d[f"{c}_movil"] = d[c].rolling(15, min_periods=7, center=True).median()
    return d


def detectar_cambio(diario: pd.DataFrame, p: Parametros, col="Desbalance_I_pct"):
    """5.6.2: fecha con el mayor cambio de nivel (ventanas de N días antes/después)."""
    serie = diario[col].dropna()
    filas = []
    dv = p.dias_ventana
    for t in serie.loc[p.ventana_busqueda[0]:p.ventana_busqueda[1]].index:
        antes = serie.loc[t - pd.Timedelta(days=dv): t - pd.Timedelta(days=1)]
        despues = serie.loc[t: t + pd.Timedelta(days=dv - 1)]
        if len(antes) >= dv // 2 and len(despues) >= dv // 2:
            filas.append({"fecha": t, "mediana_antes": antes.median(),
                          "mediana_despues": despues.median()})
    if not filas:
        return pd.DataFrame(), None
    saltos = pd.DataFrame(filas).set_index("fecha")
    saltos["salto_pp"] = saltos["mediana_despues"] - saltos["mediana_antes"]
    return saltos, saltos["salto_pp"].abs().idxmax()


def comparar_periodos(op: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """5.6.3: medianas y P95 Antes vs Después (sin transición)."""
    cmp = op[op["periodo"] != "Transición"]
    vars_cmp = (["Desbalance_I_pct", "Desbalance_kW_pct", "Desbalance_V_pct"]
                + FASES_I + FASES_KW + FASES_FP + ["kW_Total", "I_Prom", "V_LN_Prom"])
    med = cmp.groupby("periodo")[vars_cmp].median().T.reindex(columns=["Antes", "Después"])
    med["diferencia"] = med["Después"] - med["Antes"]
    med["cambio_%"] = med["diferencia"] / med["Antes"] * 100
    p95 = (cmp.groupby("periodo")[["Desbalance_I_pct", "Desbalance_kW_pct", "Desbalance_V_pct"]]
              .quantile(0.95).T.reindex(columns=["Antes", "Después"]))
    p95.columns = ["P95 Antes", "P95 Después"]
    return med, p95


def desbalance_por_banda(op: pd.DataFrame, p: Parametros, min_n: int = 50) -> pd.DataFrame:
    """5.6.5: desbalance de corriente por bandas de 10 kW, en cada período."""
    cmp = op[op["periodo"] != "Transición"]
    if cmp.empty:
        return pd.DataFrame()
    bandas = np.arange(p.umbral_produccion_kw, cmp["kW_Total"].max() + 10, 10)
    tmp = cmp.assign(banda_kW=pd.cut(cmp["kW_Total"], bandas))
    pb = (tmp.groupby(["banda_kW", "periodo"], observed=True)["Desbalance_I_pct"]
             .agg(["median", "size"]).unstack("periodo"))
    if ("size", "Antes") not in pb.columns or ("size", "Después") not in pb.columns:
        return pd.DataFrame()
    pb = pb[(pb["size"][["Antes", "Después"]] >= min_n).all(axis=1)]
    out = pd.DataFrame({
        "kW_centro": [iv.mid for iv in pb.index],
        "Antes": pb[("median", "Antes")].values,
        "Después": pb[("median", "Después")].values,
        "n_Antes": pb[("size", "Antes")].values,
        "n_Después": pb[("size", "Después")].values,
    })
    return out


def reparto_y_fp(op: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """5.6.6: % de corriente por fase y FP total por fase."""
    cmp = op[op["periodo"] != "Transición"]
    reparto = (cmp[FASES_I].div(cmp[FASES_I].sum(axis=1), axis=0).mul(100)
                  .groupby(cmp["periodo"]).median().T.reindex(columns=["Antes", "Después"]))
    fp = cmp.groupby("periodo")[FASES_FP].median().T.reindex(columns=["Antes", "Después"])
    return reparto, fp
