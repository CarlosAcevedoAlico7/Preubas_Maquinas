"""Sección 5 del notebook: análisis exploratorio (excepto 5.6, en desbalance.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import FASES_I, FASES_KW, FASES_V, H_INTERVALO, Parametros


def potencia_diaria(limpio: pd.DataFrame) -> pd.DataFrame:
    """5.1: promedio y máximo diario de kW_Total (días con ≥ 50 % de datos)."""
    diario = limpio["kW_Total"].resample("D").agg(["mean", "max", "count"])
    diario.loc[diario["count"] < 48, ["mean", "max"]] = np.nan
    return diario


def percentiles_potencia(limpio: pd.DataFrame) -> pd.Series:
    """5.2: estadísticos de la distribución de potencia."""
    return limpio["kW_Total"].dropna().describe(
        percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])


def perfil_semana_hora(limpio: pd.DataFrame, solo_desde_kw: float | None = None) -> pd.DataFrame:
    """5.3: kW_Total promedio por día de la semana y hora."""
    d = limpio if solo_desde_kw is None else limpio[limpio["kW_Total"] >= solo_desde_kw]
    return d.pivot_table(index="dia_semana", columns="hora", values="kW_Total", aggfunc="mean")


def energia_mensual(limpio: pd.DataFrame) -> pd.DataFrame:
    """5.4: energía mensual con el contador, cobertura y horas con potencia cero."""
    return limpio.groupby("mes").agg(
        kWh=("kWh_intervalo", "sum"),
        cobertura_pct=("kWh_intervalo", lambda s: s.notna().mean() * 100),
        horas_potencia_cero=("potencia_cero", lambda s: s.sum() * H_INTERVALO),
        dias=("fecha", "nunique"),
    )


def resumen_fases(limpio: pd.DataFrame) -> pd.DataFrame:
    """5.5: medianas y P95 por fase con la máquina operando (kW_Total > 0)."""
    operando = limpio[limpio["kW_Total"] > 0]
    cols = FASES_I + FASES_KW + ["Desbalance_I_pct", "Desbalance_kW_pct", "Desbalance_V_pct"]
    return pd.DataFrame({"mediana": operando[cols].median(),
                         "p95": operando[cols].quantile(0.95)})


def eventos_voltaje(limpio: pd.DataFrame, p: Parametros) -> tuple[pd.DataFrame, pd.Series]:
    """5.7: intervalos con alguna fase fuera de ±desv de su mediana."""
    v_ref = limpio[FASES_V].median()
    desv = (limpio[FASES_V] / v_ref - 1).abs()
    eventos = limpio.loc[(desv > p.desv_voltaje).any(axis=1),
                         FASES_V + ["V_LL_Prom", "kW_Total"]]
    return eventos, v_ref


def bloques_potencia_cero(limpio: pd.DataFrame) -> pd.DataFrame:
    """5.8: bloques continuos con potencia exactamente cero."""
    cero = limpio["potencia_cero"].astype(int)
    bloques = (cero.diff().fillna(cero) == 1).cumsum().where(cero == 1)
    tmp = pd.DataFrame({"bloque": bloques, "t": limpio.index}).dropna(subset=["bloque"])
    if tmp.empty:
        return pd.DataFrame(columns=["inicio", "fin", "horas"])
    return (tmp.groupby("bloque")
               .agg(inicio=("t", "min"), fin=("t", "max"), n=("t", "size"))
               .assign(horas=lambda d: d["n"] * H_INTERVALO)
               .drop(columns="n")
               .sort_values("horas", ascending=False)
               .reset_index(drop=True))
