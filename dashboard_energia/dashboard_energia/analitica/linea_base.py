"""Sección 7 del notebook: línea base energética (ISO 50006), CUSUM e indicador de desempeño."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import H_INTERVALO, Parametros

VARS_LB = ["h_produccion", "h_carga_reducida"]


def tabla_diaria(ei: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    """7.1: energía y horas por estado de cada día, con marca de validez y período."""
    es = ei["estado"]
    dia = pd.DataFrame({
        "kWh": ei["energia_kWh"].resample("D").sum(min_count=1),
        "h_produccion": (es == "Producción").resample("D").sum() * H_INTERVALO,
        "h_carga_reducida": (es == "Carga reducida").resample("D").sum() * H_INTERVALO,
        "h_parada": (es == "Parada").resample("D").sum() * H_INTERVALO,
        "kWh_carga_reducida": ei["energia_kWh"].where(es == "Carga reducida").resample("D").sum(),
        "intervalos": ei["kW_Total"].resample("D").size(),
        "cobertura_kWh": ei["energia_kWh"].notna().resample("D").mean(),
        "cobertura_kW": ei["kW_Total"].notna().resample("D").mean(),
    })
    dia["valido"] = ((dia["intervalos"] == 96)
                     & (dia["cobertura_kWh"] >= p.cobertura_min)
                     & (dia["cobertura_kW"] >= p.cobertura_min))
    idx = dia.index.to_series()
    dia["periodo"] = np.select([idx.between(*p.periodo_base), idx.between(*p.periodo_reporte)],
                               ["Base", "Reporte"], default="Fuera")
    return dia


def _matriz(df, vars_x):
    return np.column_stack([np.ones(len(df))] + [df[v].to_numpy(float) for v in vars_x])


def ajustar(df: pd.DataFrame, vars_x=VARS_LB) -> pd.Series:
    coef, *_ = np.linalg.lstsq(_matriz(df, vars_x), df["kWh"].to_numpy(float), rcond=None)
    return pd.Series(coef, index=["a"] + list(vars_x))


def predecir(df: pd.DataFrame, coef: pd.Series, vars_x=VARS_LB) -> pd.Series:
    return pd.Series(_matriz(df, vars_x) @ coef.to_numpy(), index=df.index)


def metricas(y: pd.Series, yhat: pd.Series, p: int) -> pd.Series:
    n, media = len(y), y.mean()
    resid = y - yhat
    return pd.Series({
        "n": n,
        "R²": 1 - (resid ** 2).sum() / ((y - media) ** 2).sum(),
        "CV(RMSE) %": np.sqrt((resid ** 2).sum() / (n - p)) / media * 100,
        "NMBE %": resid.sum() / ((n - p) * media) * 100,
    })


def modelo_linea_base(dia: pd.DataFrame) -> dict:
    """7.2–7.3: ajuste en período base, métricas, CUSUM y resumen mensual."""
    base = dia[dia["valido"] & (dia["periodo"] == "Base")]
    if len(base) < 10:
        return {}
    coef = ajustar(base)
    k = len(VARS_LB) + 1
    met_d = metricas(base["kWh"], predecir(base, coef), k)
    mes_b = base.assign(pred=predecir(base, coef)).resample("MS")[["kWh", "pred"]].sum()
    met_m = metricas(mes_b["kWh"], mes_b["pred"], k)

    validos = dia[dia["valido"] & dia["periodo"].isin(["Base", "Reporte"])].copy()
    validos["esperado"] = predecir(validos, coef)
    validos["desviacion_kWh"] = validos["kWh"] - validos["esperado"]
    validos["cusum_MWh"] = validos["desviacion_kWh"].cumsum() / 1000

    mensual = validos.resample("MS").agg({"kWh": "sum", "esperado": "sum", "periodo": "first"})
    mensual["dias_validos"] = validos["kWh"].resample("MS").size()
    mensual["desviacion_kWh"] = mensual["kWh"] - mensual["esperado"]
    mensual["desviacion_%"] = mensual["desviacion_kWh"] / mensual["esperado"] * 100
    mensual = mensual[mensual["dias_validos"] > 0]
    mensual.index = mensual.index.strftime("%Y-%m")

    return {"coef": coef, "metricas": pd.DataFrame({"diaria": met_d, "mensual": met_m}),
            "validos": validos, "mensual": mensual}


def indicador_kw_produccion(ei: pd.DataFrame, dia: pd.DataFrame, p: Parametros):
    """7.4: kW medio en producción por día, con banda P10–P90 del período base."""
    kw = ei.loc[ei["estado"] == "Producción", "kW_Total"].resample("D").mean().reindex(dia.index)
    kw[dia["h_produccion"] < 6] = np.nan
    ref = kw.loc[p.periodo_base[0]:p.periodo_base[1]]
    out = pd.DataFrame({"kW_prod": kw,
                        "mediana_movil_30d": kw.rolling(30, min_periods=15).median()})
    return out, (ref.quantile(0.10), ref.quantile(0.90))
