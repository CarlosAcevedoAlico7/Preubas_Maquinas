"""Sección 6 del notebook: energía improductiva."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import ESTADOS, FREQ, H_INTERVALO, Parametros


def clasificar_estado(kw: pd.Series, umbral_prod: float, umbral_parada: float) -> pd.Series:
    estado = np.select([kw.isna(), kw < umbral_parada, kw < umbral_prod],
                       ["Sin dato", "Parada", "Carga reducida"], default="Producción")
    return pd.Series(estado, index=kw.index)


def tabla_estados(limpio: pd.DataFrame, p: Parametros) -> tuple[pd.DataFrame, dict]:
    """6.1: estado de cada intervalo y energía de los 15 min siguientes."""
    ei = limpio[["kW_Total", "kWh_intervalo", "mes"]].copy()
    ei["estado"] = clasificar_estado(ei["kW_Total"], p.umbral_produccion_kw, p.umbral_parada_kw)
    ei["energia_kWh"] = ei["kWh_intervalo"].shift(-1)
    kwh = limpio["kWh_Acumulado"].dropna()
    total = float(kwh.iloc[-1] - kwh.iloc[0]) if len(kwh) > 1 else np.nan
    asignada = float(ei["energia_kWh"].sum())
    return ei, {"energia_contador": total, "energia_asignada": asignada,
                "energia_no_asignada": total - asignada}


def balance_estados(ei: pd.DataFrame, p: Parametros) -> tuple[pd.DataFrame, float]:
    """6.2: horas y energía por estado; % de energía improductiva."""
    b = (ei.groupby("estado")
           .agg(horas=("estado", lambda s: len(s) * H_INTERVALO), kWh=("energia_kWh", "sum"))
           .reindex(ESTADOS).fillna(0))
    b["%_tiempo"] = b["horas"] / b["horas"].sum() * 100
    b["%_energia"] = b["kWh"] / b["kWh"].sum() * 100
    b["kW_medio"] = b["kWh"] / b["horas"].replace(0, np.nan)
    if p.tarifa_cop_kwh:
        b["costo_COP"] = b["kWh"] * p.tarifa_cop_kwh
    clasif = b.loc[["Producción", "Carga reducida", "Parada"], "kWh"].sum()
    pct = b.loc["Carga reducida", "kWh"] / clasif * 100 if clasif else np.nan
    return b, pct


def mensual_estados(ei: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """6.3: energía y horas por mes y estado, con % de energía improductiva."""
    mensual = ei.pivot_table(index="mes", columns="estado", values="energia_kWh",
                             aggfunc="sum", fill_value=0).reindex(columns=ESTADOS, fill_value=0)
    horas = (pd.crosstab(ei["mes"], ei["estado"]).reindex(columns=ESTADOS, fill_value=0)
             * H_INTERVALO)
    clasif = mensual[["Producción", "Carga reducida", "Parada"]].sum(axis=1)
    mensual["%_improductiva"] = mensual["Carga reducida"] / clasif.replace(0, np.nan) * 100
    return mensual, horas


def bloques_estado(ei: pd.DataFrame) -> pd.DataFrame:
    bloque = (ei["estado"] != ei["estado"].shift()).cumsum()
    b = (ei.assign(bloque=bloque, t=ei.index)
           .groupby("bloque")
           .agg(estado=("estado", "first"), inicio=("t", "min"), fin=("t", "max"),
                intervalos=("t", "size"), kWh=("energia_kWh", "sum"),
                kW_medio=("kW_Total", "mean")))
    b["fin"] = b["fin"] + pd.Timedelta(FREQ)
    b["horas"] = b["intervalos"] * H_INTERVALO
    b["estado_previo"] = b["estado"].shift()
    b["estado_siguiente"] = b["estado"].shift(-1)
    return b


def episodios_carga_reducida(bloques: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """6.4: episodios de carga reducida clasificados por estado previo y siguiente."""
    ep = bloques[bloques["estado"] == "Carga reducida"].copy()
    reglas = [
        (ep["estado_previo"] == "Parada") & (ep["estado_siguiente"] == "Producción"),
        (ep["estado_previo"] == "Producción") & (ep["estado_siguiente"] == "Parada"),
        (ep["estado_previo"] == "Producción") & (ep["estado_siguiente"] == "Producción"),
    ]
    ep["tipo"] = np.select(reglas, ["Arranque", "Apagado", "Caída en producción"], default="Otro")
    resumen = (ep.groupby("tipo")
                 .agg(episodios=("kWh", "size"), horas=("horas", "sum"),
                      kWh=("kWh", "sum"), duracion_mediana_h=("horas", "median"))
                 .sort_values("kWh", ascending=False))
    resumen["%_energia_improductiva"] = resumen["kWh"] / resumen["kWh"].sum() * 100
    return ep, resumen


def duracion_caidas(ep: pd.DataFrame) -> pd.DataFrame:
    caidas = ep[ep["tipo"] == "Caída en producción"]
    rangos = pd.cut(caidas["horas"], [0, 0.25, 0.5, 1, 2, 4, 8, np.inf],
                    labels=["15 min", "30 min", "≤1 h", "1–2 h", "2–4 h", "4–8 h", "> 8 h"])
    return pd.DataFrame({"episodios": caidas.groupby(rangos, observed=False).size(),
                         "kWh": caidas["kWh"].groupby(rangos, observed=False).sum()})


def arranques(ei: pd.DataFrame, bloques: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    """6.5: tiempo y energía hasta producción sostenida después de paradas largas."""
    largas = bloques[(bloques["estado"] == "Parada") & (bloques["horas"] >= p.min_parada_arranque_h)]
    filas = []
    for _, par in largas.iterrows():
        tramo = ei.loc[par["fin"]: par["fin"] + pd.Timedelta(hours=72)]
        encendida = tramo.index[tramo["kW_Total"] >= p.umbral_parada_kw]
        if len(encendida) == 0:
            continue
        t0 = encendida[0]
        prod = (tramo.loc[t0:, "kW_Total"] >= p.umbral_produccion_kw).astype(int)
        sost = prod.rolling(p.intervalos_estable).sum() == p.intervalos_estable
        if not sost.any():
            continue
        t_est = sost.idxmax() - pd.Timedelta(FREQ) * (p.intervalos_estable - 1)
        ventana = ei.loc[t0: t_est - pd.Timedelta(FREQ)]
        filas.append({
            "parada_inicio": par["inicio"], "parada_horas": par["horas"],
            "encendido": t0, "produccion_estable": t_est,
            "horas_arranque": (t_est - t0).total_seconds() / 3600,
            "kWh_arranque": ventana["energia_kWh"].sum(),
            "kW_medio_arranque": ventana["kW_Total"].mean(),
        })
    a = pd.DataFrame(filas)
    if len(a):
        a = a.drop_duplicates("produccion_estable", keep="last").reset_index(drop=True)
        if p.tarifa_cop_kwh:
            a["costo_COP"] = a["kWh_arranque"] * p.tarifa_cop_kwh
    return a


def sensibilidad_umbral(ei: pd.DataFrame, p: Parametros,
                        umbrales=(120, 150, 180, 200, 220)) -> pd.DataFrame:
    """6.6: % de energía improductiva con distintos umbrales de producción."""
    filas = []
    for u in sorted(set(list(umbrales) + [p.umbral_produccion_kw])):
        est = clasificar_estado(ei["kW_Total"], u, p.umbral_parada_kw)
        e = ei["energia_kWh"].groupby(est).sum()
        h = est.value_counts() * H_INTERVALO
        clasif = e.reindex(["Producción", "Carga reducida", "Parada"]).fillna(0).sum()
        filas.append({"umbral_kW": u,
                      "horas_carga_reducida": h.get("Carga reducida", 0),
                      "kWh_improductiva": e.get("Carga reducida", 0),
                      "%_energia_improductiva": e.get("Carga reducida", 0) / clasif * 100})
    return pd.DataFrame(filas).set_index("umbral_kW")
