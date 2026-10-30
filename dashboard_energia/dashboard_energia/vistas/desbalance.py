import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ui.estado import rango, resultados
from ui.graficos import (AZUL, COLOR_PERIODO, GRIS, NARANJA, ROJO, banda_transicion, estilo,
                         linea_vertical, mostrar, recortar)

PANELES = [("Desbalance_I_pct", "Desbalance de corriente (%)"),
           ("Desbalance_kW_pct", "Desbalance de potencia activa (%)"),
           ("Desbalance_V_pct", "Desbalance de voltaje (%)")]


def render():
    r, rg = resultados(), rango()
    p = r.parametros
    st.title("Fases y desbalance")
    st.caption(f"Solo intervalos en producción (kW_Total ≥ {p.umbral_produccion_kw:g} kW). "
               f"Antes < {p.fecha_filtro} ≤ Transición < {p.fin_transicion} ≤ Después.")

    cmp_ = r.comparacion
    c = st.columns(4)
    for col, (var, nombre) in zip(c[:3], PANELES):
        if var in cmp_.index:
            a, d = cmp_.loc[var, "Antes"], cmp_.loc[var, "Después"]
            col.metric(nombre.replace(" (%)", ""), f"{d:.2f} %", f"{d - a:+.2f} p.p. vs. antes",
                       delta_color="inverse")
    if r.fecha_cambio is not None:
        s = r.saltos.loc[r.fecha_cambio]
        c[3].metric("Mayor cambio de nivel detectado", f"{r.fecha_cambio:%d-%b-%Y}",
                    f"{s['mediana_antes']:.1f} % → {s['mediana_despues']:.1f} %", delta_color="off")

    # 5.6.1
    dd = recortar(r.desb_diario, rg)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=[t for _, t in PANELES])
    for i, (col, _) in enumerate(PANELES, start=1):
        fig.add_scatter(x=dd.index, y=dd[col], mode="markers", marker=dict(size=4, color=GRIS, opacity=0.5),
                        name="Mediana diaria", showlegend=i == 1, legendgroup="d", row=i, col=1)
        fig.add_scatter(x=dd.index, y=dd[f"{col}_movil"], mode="lines", line=dict(color=AZUL, width=2),
                        name="Media móvil 15 días", showlegend=i == 1, legendgroup="m", row=i, col=1)
    banda_transicion(fig, p.fecha_filtro, p.fin_transicion, row="all", col=1)
    for a in fig.layout.annotations:
        if a.xref == "paper":  # solo títulos de subgráficas
            a.update(x=0, xanchor="left", font=dict(size=12))
    mostrar(estilo(fig, 620))

    # 5.6.2
    if len(r.saltos):
        c1, c2 = st.columns([3, 2])
        with c1:
            sl = r.saltos
            fig = go.Figure(go.Scatter(x=sl.index, y=sl["salto_pp"], mode="lines",
                                       line=dict(color=AZUL, width=2), name="Δ mediana"))
            fig.add_hline(y=0, line_color=GRIS, line_width=1)
            banda_transicion(fig, p.fecha_filtro, p.fin_transicion)
            linea_vertical(fig, r.fecha_cambio, f"Máximo: {r.fecha_cambio:%Y-%m-%d}", color=ROJO)
            mostrar(estilo(fig, 280, f"Cambio de nivel del desbalance de corriente "
                                     f"({p.dias_ventana} días después − antes)", y="p.p.", leyenda=False))
        with c2:
            st.markdown("**Interpretación**")
            st.markdown(
                "- Si el máximo cae **cerca de la transición**, el cambio es consistente con el filtro.\n"
                "- Si el **desbalance de potencia activa** se mueve igual que el de corriente, cambió el "
                "**reparto de la carga** entre fases (el filtro no altera la potencia activa).\n"
                "- La señal más confiable de acción del filtro es la **mejora del FP por fase**.")

    # 5.6.3
    st.subheader("Comparación antes / después (medianas)")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.dataframe(cmp_.round(3), use_container_width=True, height=420)
    with c2:
        st.dataframe(r.p95.round(2), use_container_width=True)
        st.dataframe(r.periodos, use_container_width=True,
                     column_config={"desde": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                                    "hasta": st.column_config.DatetimeColumn(format="YYYY-MM-DD")})

    # 5.6.4 y 5.6.5
    cmp = r.op[r.op["periodo"] != "Transición"]
    c1, c2 = st.columns(2)
    with c1:
        var = st.radio("Distribución de", ["Desbalance_I_pct", "Desbalance_kW_pct"], horizontal=True,
                       format_func=lambda v: "corriente" if v.endswith("I_pct") else "potencia activa")
        lim = cmp[var].quantile(0.995)
        fig = go.Figure()
        for per in ["Antes", "Después"]:
            datos = cmp.loc[cmp["periodo"] == per, var].dropna()
            fig.add_histogram(x=datos, histnorm="probability density", name=f"{per} (mediana {datos.median():.1f} %)",
                              xbins=dict(start=0, end=lim, size=lim / 80), opacity=0.6,
                              marker_color=COLOR_PERIODO[per], marker_line_width=0)
        fig.update_layout(barmode="overlay", hovermode="closest")
        mostrar(estilo(fig, 320, "Distribución en cada período", y="Densidad", x="%"))
    with c2:
        pb = r.por_banda
        if len(pb):
            fig = go.Figure()
            for per in ["Antes", "Después"]:
                fig.add_scatter(x=pb["kW_centro"], y=pb[per], mode="lines+markers", name=per,
                                line=dict(color=COLOR_PERIODO[per], width=2), marker=dict(size=8))
            mostrar(estilo(fig, 380, "Desbalance de corriente por nivel de carga (control)",
                           y="Mediana (%)", x="kW_Total (centro de banda de 10 kW)"))

    # 5.6.6
    st.subheader("Reparto de corriente y factor de potencia por fase")
    c1, c2 = st.columns(2)
    fases = ["Fase A", "Fase B", "Fase C"]
    with c1:
        fig = go.Figure()
        for per in ["Antes", "Después"]:
            fig.add_bar(x=fases, y=r.reparto[per], name=per, marker_color=COLOR_PERIODO[per],
                        hovertemplate="%{y:.2f} %")
        fig.add_hline(y=100 / 3, line_dash="dash", line_color=GRIS,
                      annotation_text="Balance ideal 33,3 %", annotation_position="top right")
        fig.update_yaxes(range=[28, 38])
        mostrar(estilo(fig, 320, "% de la corriente total", y="%"))
    with c2:
        fig = go.Figure()
        for per in ["Antes", "Después"]:
            fig.add_bar(x=fases, y=r.fp[per], name=per, marker_color=COLOR_PERIODO[per],
                        hovertemplate="%{y:.3f}")
        fig.update_yaxes(range=[0.7, 1.0])
        mostrar(estilo(fig, 320, "Factor de potencia total por fase (P / V·I)", y="FP"))

    st.subheader("Resumen por fase (máquina operando)")
    st.dataframe(r.fases.round(2).T, use_container_width=True)
