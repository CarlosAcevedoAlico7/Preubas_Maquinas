"""Sección 8 del notebook: detección de anomalías explicable (z robusto)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import FASES_FP, FASES_V, Parametros

NOMBRES = {
    "kW_medio_produccion": ("kW medio en producción", "kW"),
    "desbalance_kW_pct": ("Desbalance de potencia activa", "%"),
    "desbalance_I_pct": ("Desbalance de corriente", "%"),
    "desbalance_V_pct": ("Desbalance de voltaje", "%"),
    "FP_medio": ("Factor de potencia medio", ""),
    "V_fase_minimo": ("Voltaje mínimo de fase", "V"),
    "pct_energia_improductiva": ("% energía improductiva (últimos 7 días)", "%"),
    "desviacion_LB_pct": ("Desviación vs. línea base", "%"),
}
ESCALA_MIN_REL = 0.01
ESCALA_MIN_ABS = {"desbalance_kW_pct": 0.2, "desbalance_I_pct": 0.2, "desbalance_V_pct": 0.05,
                  "FP_medio": 0.005, "pct_energia_improductiva": 1.0, "desviacion_LB_pct": 0.5}


def indicadores_diarios(limpio, ei, dia, validos, p: Parametros) -> pd.DataFrame:
    """8.1: indicadores diarios vigilados."""
    en_prod = limpio[ei["estado"] == "Producción"]
    n_prod = en_prod["kW_Total"].resample("D").size().reindex(dia.index, fill_value=0)
    ind = pd.DataFrame({
        "kW_medio_produccion": en_prod["kW_Total"].resample("D").mean(),
        "desbalance_kW_pct": en_prod["Desbalance_kW_pct"].resample("D").median(),
        "desbalance_I_pct": en_prod["Desbalance_I_pct"].resample("D").median(),
        "desbalance_V_pct": en_prod["Desbalance_V_pct"].resample("D").median(),
        "FP_medio": en_prod[FASES_FP].mean(axis=1).resample("D").median(),
    }).reindex(dia.index)
    ind[n_prod < p.min_intervalos_prod] = np.nan
    ind["V_fase_minimo"] = limpio[FASES_V].min(axis=1).resample("D").min().reindex(dia.index)
    e_red = dia["kWh_carga_reducida"].where(dia["valido"]).rolling(7, min_periods=5).sum()
    e_tot = dia["kWh"].where(dia["valido"]).rolling(7, min_periods=5).sum()
    ind["pct_energia_improductiva"] = e_red / e_tot * 100
    dia_normal = (dia["h_parada"] == 0) & (dia["h_produccion"] >= 6)
    if validos is not None and len(validos):
        ind["desviacion_LB_pct"] = ((validos["desviacion_kWh"] / validos["esperado"] * 100)
                                    .reindex(dia.index).where(dia_normal))
    else:
        ind["desviacion_LB_pct"] = np.nan
    return ind


def referencia(ind: pd.DataFrame, p: Parametros) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Mediana y escala robusta (MAD con piso) del período base; puntaje z diario."""
    ref = ind.loc[p.periodo_base[0]:p.periodo_base[1]]
    mediana = ref.median()
    escala = 1.4826 * (ref - mediana).abs().median()
    piso = np.maximum(ESCALA_MIN_REL * mediana.abs(),
                      pd.Series(ESCALA_MIN_ABS).reindex(ind.columns).fillna(0))
    escala = np.maximum(escala.fillna(0), piso)
    z = (ind - mediana) / escala
    return mediana, escala, z


def generar_alertas(ind, z, mediana, dia, p: Parametros) -> pd.DataFrame:
    """8.2: reglas puntual y sostenida, agrupadas en episodios, con explicación en texto."""
    filas = []
    z_rol = z.rolling(p.dias_sostenido, min_periods=p.dias_sostenido // 2 + 1).median()
    en_episodio = pd.DataFrame(False, index=z.index, columns=z.columns)
    for col in ind.columns:
        activo = z_rol[col].abs() >= p.z_sostenido
        signo = np.sign(z_rol[col]).where(activo, 0)
        grupo = (signo != signo.shift()).cumsum()
        for _, g in z_rol[col][activo].groupby(grupo[activo]):
            a, b = g.index.min(), g.index.max()
            en_episodio.loc[a - pd.Timedelta(days=p.dias_sostenido - 1):b, col] = True
            filas.append({"inicio": a, "fin": b, "indicador": col, "regla": "Sostenida",
                          "valor": ind[col].loc[a:b].median(), "z": g.median()})
    for col in ind.columns:
        for fecha in z.index[(z[col].abs() >= p.z_puntual) & ~en_episodio[col]]:
            filas.append({"inicio": fecha, "fin": fecha, "indicador": col, "regla": "Puntual",
                          "valor": ind.at[fecha, col], "z": z.at[fecha, col]})

    cols = ["inicio", "fin", "regla", "indicador", "valor", "z", "dias", "referencia",
            "cambio_%", "con_parada", "explicacion"]
    if not filas:
        return pd.DataFrame(columns=cols)
    al = pd.DataFrame(filas)
    al["dias"] = (al["fin"] - al["inicio"]).dt.days + 1
    al["referencia"] = al["indicador"].map(mediana)
    al["cambio_%"] = (al["valor"] / al["referencia"] - 1) * 100
    al["con_parada"] = [bool((dia.loc[a:b, "h_parada"] > 0).any())
                        for a, b in zip(al["inicio"], al["fin"])]

    def explicar(r):
        nombre, u = NOMBRES[r["indicador"]]
        sentido = "por encima" if r["z"] > 0 else "por debajo"
        txt = (f"{nombre} {sentido} de lo normal: {r['valor']:.2f} {u} frente a "
               f"{r['referencia']:.2f} {u} de referencia")
        if abs(r["referencia"]) > 1 and abs(r["cambio_%"]) < 1000:
            txt += f" ({r['cambio_%']:+.0f} %)"
        if r["regla"] == "Sostenida":
            txt += f", durante {r['dias']} días"
        if r["con_parada"]:
            txt += ". Incluye días con parada"
        return txt

    al["explicacion"] = al.apply(explicar, axis=1)
    return al.sort_values("inicio").reset_index(drop=True)[cols]
