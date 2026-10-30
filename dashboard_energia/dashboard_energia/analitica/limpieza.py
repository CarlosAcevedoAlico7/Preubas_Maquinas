"""Secciones 3 y 4 del notebook: validación de calidad y dataset analítico de 15 min."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import (COL_FECHA, COLS_NUM, FASES_FP, FASES_I, FASES_KW, FASES_V, FREQ)


def convertir_tipos(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """3.1–3.2: 'NULL' de texto -> NaN, fecha datetime2 -> datetime. Devuelve (df, resumen)."""
    df = raw.copy()
    n_null_txt = (df[COLS_NUM].astype(str).apply(lambda s: s.str.upper()) == "NULL").sum()
    df[COLS_NUM] = (df[COLS_NUM].replace({"NULL": np.nan, "null": np.nan})
                    .apply(pd.to_numeric, errors="coerce"))
    if not pd.api.types.is_datetime64_any_dtype(df[COL_FECHA]):
        df[COL_FECHA] = pd.to_datetime(df[COL_FECHA].astype(str).str.slice(0, 19),
                                       format="%Y-%m-%d %H:%M:%S", errors="coerce")
    else:
        df[COL_FECHA] = df[COL_FECHA].dt.tz_localize(None) if df[COL_FECHA].dt.tz else df[COL_FECHA]
    df[COL_FECHA] = df[COL_FECHA].astype("datetime64[ns]")
    df = df.dropna(subset=[COL_FECHA]).sort_values(COL_FECHA).reset_index(drop=True)
    resumen = pd.DataFrame({
        "NULL_texto": n_null_txt,
        "faltantes": df[COLS_NUM].isna().sum(),
        "pct_faltante": df[COLS_NUM].isna().mean() * 100,
    })
    return df, resumen


def diagnostico_registros(df: pd.DataFrame) -> dict:
    """3.3–3.4: duplicados, registros fuera de grilla y huecos."""
    f = df[COL_FECHA]
    fuera = (f.dt.minute % 15 != 0) | (f.dt.second != 0)
    delta = f.diff().dropna()
    mediana = delta.median()
    huecos = delta[delta > 3 * mediana].sort_values(ascending=False)
    tabla_huecos = pd.DataFrame({
        "inicio": df.loc[huecos.index - 1, COL_FECHA].values,
        "fin": df.loc[huecos.index, COL_FECHA].values,
        "duracion_h": huecos.dt.total_seconds().values / 3600,
    })
    return {
        "registros": len(df),
        "desde": f.min(), "hasta": f.max(),
        "duplicados": int(df.duplicated().sum()),
        "marcas_repetidas": int(f.duplicated().sum()),
        "fuera_grilla": int(fuera.sum()),
        "intervalo_mediano": mediana,
        "pct_intervalo_mediano": float((delta == mediana).mean() * 100),
        "huecos": tabla_huecos,
    }


def faltantes_por_mes(df: pd.DataFrame,
                      cols=("V_LN_Prom", "I_Prom", "kW_FaseA", "kW_Demanda", "kWh_Acumulado")):
    """3.5: % de faltantes por mes y variable."""
    mes = df[COL_FECHA].dt.to_period("M").astype(str)
    return df[list(cols)].isna().groupby(mes).mean().mul(100)


def chequeos_fisicos(df: pd.DataFrame) -> pd.Series:
    """3.6: relaciones físicas que confirman unidades."""
    suma_fases = df[FASES_KW].sum(axis=1, min_count=3)
    horas = df[COL_FECHA].diff().dt.total_seconds() / 3600
    inc_kwh = df["kWh_Acumulado"].diff()
    mask = suma_fases.shift().notna() & inc_kwh.notna() & (inc_kwh >= 0) & (horas > 0)
    e_contador = inc_kwh[mask].sum()
    e_integrada = (suma_fases.shift() * horas)[mask].sum()
    return pd.Series({
        "V_LL_Prom / V_LN_Prom (≈1,732 trifásico)":
            (df["V_LL_Prom"] / df["V_LN_Prom"]).median(),
        "|prom(V fases) − V_LN_Prom|":
            (df[FASES_V].mean(axis=1) - df["V_LN_Prom"]).abs().median(),
        "|prom(I fases) − I_Prom|":
            (df[FASES_I].mean(axis=1) - df["I_Prom"]).abs().median(),
        "(kW_A+B+C) / kW_Demanda":
            (suma_fases / df["kW_Demanda"]).replace(np.inf, np.nan).median(),
        "Correlación suma fases vs kW_Demanda": suma_fases.corr(df["kW_Demanda"]),
        "Incrementos negativos de kWh_Acumulado": float((inc_kwh < 0).sum()),
        "Energía integrada (kW×Δt) / contador":
            e_integrada / e_contador if e_contador else np.nan,
    }, name="valor")


def desbalance_pct(x: pd.DataFrame) -> pd.Series:
    """Máxima desviación respecto al promedio de fases, en % (definición NEMA)."""
    prom = x.mean(axis=1)
    return (x.sub(prom, axis=0).abs().max(axis=1) / prom * 100).where(prom > 0)


def construir_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Sección 4: grilla de 15 min con huecos explícitos e indicadores derivados."""
    limpio = df.copy()
    limpio["grid"] = limpio[COL_FECHA].dt.round(FREQ)
    limpio["desfase_s"] = (limpio[COL_FECHA] - limpio["grid"]).dt.total_seconds().abs()
    n_desfasados = int((limpio["desfase_s"] > 0).sum())
    limpio = limpio.sort_values(["grid", "desfase_s"])
    n_dup = int(limpio["grid"].duplicated().sum())
    limpio = (limpio.drop_duplicates("grid", keep="first")
                    .drop(columns=[COL_FECHA, "desfase_s"])
                    .rename(columns={"grid": COL_FECHA})
                    .set_index(COL_FECHA).sort_index())

    con_registro = limpio.index
    grilla = pd.date_range(limpio.index.min(), limpio.index.max(), freq=FREQ, name=COL_FECHA)
    limpio = limpio.reindex(grilla)
    limpio["sin_registro"] = ~limpio.index.isin(con_registro)

    limpio["kW_Total"] = limpio[FASES_KW].sum(axis=1, min_count=3)
    limpio["kWh_intervalo"] = limpio["kWh_Acumulado"].diff()

    limpio["Desbalance_I_pct"] = desbalance_pct(limpio[FASES_I])
    limpio["Desbalance_V_pct"] = desbalance_pct(limpio[FASES_V])
    limpio["Desbalance_kW_pct"] = desbalance_pct(limpio[FASES_KW])
    for fp, v, i, p in zip(FASES_FP, FASES_V, FASES_I, FASES_KW):
        limpio[fp] = (limpio[p] * 1000 / (limpio[v] * limpio[i])).where(limpio[i] > 0)

    limpio["potencia_cero"] = limpio["kW_Total"].eq(0)
    limpio["fecha"] = limpio.index.normalize()
    limpio["hora"] = limpio.index.hour
    limpio["dia_semana"] = limpio.index.day_of_week
    limpio["mes"] = limpio.index.to_period("M").astype(str)

    resumen = {
        "Registros originales": len(df),
        "Registros desfasados ajustados": n_desfasados,
        "Duplicados eliminados tras ajuste": n_dup,
        "Puntos de la grilla de 15 min": len(limpio),
        "Puntos sin registro": int(limpio["sin_registro"].sum()),
        "Cobertura kW_Total (%)": limpio["kW_Total"].notna().mean() * 100,
        "Cobertura kW_Demanda (%)": limpio["kW_Demanda"].notna().mean() * 100,
        "Cobertura kWh_intervalo (%)": limpio["kWh_intervalo"].notna().mean() * 100,
    }
    return limpio, resumen
