import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.estado import rango, resultados
from ui.graficos import AZUL, COLOR_PERIODO, GRIS, NARANJA, estilo, linea_vertical, mostrar, recortar


def render():
    r, rg = resultados(), rango()
    p = r.parametros
    st.title("Línea base energética (ISO 50006)")
    st.caption("Modelo:  E_día = a + b · h_producción + c · h_carga_reducida  — ajustado en el "
               f"período base {p.periodo_base[0]} → {p.periodo_base[1]} con días completos "
               f"(96 intervalos, cobertura ≥ {p.cobertura_min:.0%}).")
    lb = r.lb
    if not lb:
        st.warning("El período base no tiene suficientes días válidos para ajustar el modelo.")
        return

    coef, met = lb["coef"], lb["metricas"]
    c = st.columns(5)
    c[0].metric("b · producción", f"{coef['h_produccion']:.1f} kW")
    c[1].metric("c · carga reducida", f"{coef['h_carga_reducida']:.1f} kW")
    c[2].metric("a · fijo (kWh/día)", f"{coef['a']:.0f}")
    c[3].metric("R² diario", f"{met.loc['R²', 'diaria']:.3f}")
    cv = met.loc["CV(RMSE) %", "mensual"]
    c[4].metric("CV(RMSE) mensual", f"{cv:.2f} %",
                "cumple ASHRAE 14 (≤ 15 %)" if cv <= 15 else "no cumple ASHRAE 14",
                delta_color="normal" if cv <= 15 else "inverse")

    v = lb["validos"]
    rep = v[v["periodo"] == "Reporte"]
    if len(rep):
        dev = rep["desviacion_kWh"].sum()
        st.info(f"**Período de reporte:** consumo real {rep['kWh'].sum() / 1000:,.0f} MWh frente a "
                f"{rep['esperado'].sum() / 1000:,.0f} MWh esperados → desviación acumulada "
                f"**{dev / 1000:+,.1f} MWh ({dev / rep['esperado'].sum() * 100:+.2f} %)**. "
                "Negativo = consume menos de lo esperado para la actividad que tuvo.")

    vr = recortar(v, rg)
    fig = go.Figure()
    fig.add_scatter(x=vr.index, y=vr["kWh"] / 1000, name="Real", mode="lines",
                    line=dict(color=AZUL, width=1.5))
    fig.add_scatter(x=vr.index, y=vr["esperado"] / 1000, name="Esperado (línea base)", mode="lines",
                    line=dict(color=NARANJA, width=1.5))
    linea_vertical(fig, p.periodo_reporte[0], "Inicio reporte")
    mostrar(estilo(fig, 300, "Energía diaria real y esperada", y="MWh/día"))

    fig = go.Figure(go.Scatter(x=vr.index, y=vr["cusum_MWh"], mode="lines", name="CUSUM",
                               line=dict(color=AZUL, width=2)))
    fig.add_hline(y=0, line_color=GRIS, line_width=1)
    linea_vertical(fig, p.periodo_reporte[0], "Inicio reporte")
    mostrar(estilo(fig, 280, "CUSUM: desviación acumulada (real − esperado). Baja = mejora, sube = deterioro",
                   y="MWh", leyenda=False))

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for per in ["Base", "Reporte"]:
            d = r.dia[r.dia["valido"] & (r.dia["periodo"] == per)]
            fig.add_scatter(x=d["h_produccion"], y=d["kWh"] / 1000, mode="markers", name=per,
                            marker=dict(size=8, color=COLOR_PERIODO[per], opacity=0.6,
                                        line=dict(width=1, color="rgba(255,255,255,0.8)")),
                            hovertemplate="%{x:.2f} h · %{y:.2f} MWh<extra>" + per + "</extra>")
        estilo(fig, 340, "Energía diaria frente a horas en producción", y="MWh/día",
               x="Horas en producción")
        fig.update_layout(hovermode="closest")
        mostrar(fig)
    with c2:
        st.markdown("**Métricas de ajuste (período base)**")
        st.dataframe(met.round(3), use_container_width=True)
        st.caption("Referencias ASHRAE 14: CV(RMSE) ≤ 15 % mensual / ≤ 30 % horario; "
                   "NMBE ±5 % mensual / ±10 % horario.")

    st.subheader("Resumen mensual")
    m = lb["mensual"].copy()
    m[["kWh", "esperado", "desviacion_kWh"]] = m[["kWh", "esperado", "desviacion_kWh"]] / 1000
    st.dataframe(m.rename(columns={"kWh": "Real MWh", "esperado": "Esperado MWh",
                                   "desviacion_kWh": "Desviación MWh"}).round(2),
                 use_container_width=True)

    st.subheader("Indicador de desempeño: kW medio en producción")
    k = recortar(r.kw_prod, rg)
    lo, hi = r.banda_kw_prod
    fig = go.Figure()
    fig.add_hrect(y0=lo, y1=hi, fillcolor=AZUL, opacity=0.10, line_width=0,
                  annotation_text="Rango normal base (P10–P90)", annotation_position="top left")
    fig.add_scatter(x=k.index, y=k["kW_prod"], mode="markers", name="Diario",
                    marker=dict(size=4, color=GRIS, opacity=0.6))
    fig.add_scatter(x=k.index, y=k["mediana_movil_30d"], mode="lines", name="Mediana móvil 30 días",
                    line=dict(color=AZUL, width=2))
    linea_vertical(fig, p.periodo_reporte[0], "Inicio reporte")
    mostrar(estilo(fig, 320, y="kW (= kWh por hora producida)"))
