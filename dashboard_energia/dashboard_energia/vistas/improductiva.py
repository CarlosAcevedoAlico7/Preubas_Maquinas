import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analitica import exportar_excel
from config import ESTADOS
from ui.estado import resultados
from ui.graficos import (AZUL, COLOR_ESTADO, GRIS, NARANJA, VIOLETA, AGUA, AMARILLO, estilo,
                         mostrar)

COLOR_TIPO = {"Caída en producción": AZUL, "Apagado": NARANJA, "Arranque": AGUA, "Otro": AMARILLO}


def render():
    r = resultados()
    p = r.parametros
    st.title("Energía improductiva")
    st.caption(f"Energía consumida sin producir: carga reducida entre {p.umbral_parada_kw:g} y "
               f"{p.umbral_produccion_kw:g} kW (proxy sin datos de producción). No incluye el "
               "chiller asociado ni la energía improductiva dentro de la producción.")

    b = r.balance
    c = st.columns(4)
    c[0].metric("Energía improductiva", f"{b.loc['Carga reducida', 'kWh'] / 1000:,.1f} MWh",
                f"{r.pct_improductiva:.2f} % de la energía clasificada", delta_color="off")
    c[1].metric("Horas en carga reducida", f"{b.loc['Carga reducida', 'horas']:,.0f} h")
    c[2].metric("Episodios", f"{len(r.episodios):,}")
    sens = r.sensibilidad["%_energia_improductiva"]
    c[3].metric("Sensibilidad 150–200 kW",
                f"{sens.get(150, float('nan')):.2f} – {sens.get(200, float('nan')):.2f} %")

    izq, der = st.columns([2, 3])
    with izq:
        fig = go.Figure(go.Bar(y=b.index, x=b["%_energia"], orientation="h",
                               marker_color=[COLOR_ESTADO[e] for e in b.index],
                               customdata=b[["kWh", "horas", "kW_medio"]],
                               hovertemplate="%{x:.2f} % de la energía<br>%{customdata[0]:,.0f} kWh"
                                             "<br>%{customdata[1]:,.0f} h · %{customdata[2]:.1f} kW medio"
                                             "<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        estilo(fig, 300, "Participación en la energía por estado", x="% de la energía", leyenda=False)
        fig.update_layout(hovermode="closest")
        mostrar(fig)
        cols = ["horas", "kWh", "%_tiempo", "%_energia", "kW_medio"] + (["costo_COP"] if "costo_COP" in b else [])
        st.dataframe(b[cols].round(1), use_container_width=True)
    with der:
        m = r.mensual_estados
        fig = go.Figure(go.Bar(x=m.index, y=m["Carga reducida"] / 1000, marker_color=NARANJA,
                               customdata=m["%_improductiva"],
                               hovertemplate="%{y:,.2f} MWh · %{customdata:.2f} %<extra></extra>"))
        mostrar(estilo(fig, 250, "Energía improductiva por mes", y="MWh", leyenda=False))
        fig = go.Figure(go.Scatter(x=m.index, y=m["%_improductiva"], mode="lines+markers",
                                   line=dict(color=NARANJA, width=2), marker=dict(size=8)))
        mostrar(estilo(fig, 230, "% de energía improductiva por mes", y="%", leyenda=False))

    st.subheader("Episodios de carga reducida")
    st.caption("Clasificados por el estado anterior y el siguiente: Arranque (parada → producción), "
               "Apagado (producción → parada), Caída en producción (producción → producción), Otro.")
    t = r.tipos_episodio
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(x=t.index, y=t["kWh"] / 1000,
                               marker_color=[COLOR_TIPO.get(i, GRIS) for i in t.index],
                               customdata=t[["episodios", "horas", "%_energia_improductiva"]],
                               hovertemplate="%{y:,.1f} MWh · %{customdata[2]:.1f} %<br>"
                                             "%{customdata[0]} episodios · %{customdata[1]:,.0f} h"
                                             "<extra></extra>"))
        mostrar(estilo(fig, 300, "Energía por tipo de episodio", y="MWh", leyenda=False))
    with c2:
        dc = r.duracion_caidas
        fig = go.Figure(go.Bar(x=dc.index.astype(str), y=dc["kWh"], marker_color=AZUL,
                               customdata=dc["episodios"],
                               hovertemplate="%{y:,.0f} kWh · %{customdata} episodios<extra></extra>"))
        mostrar(estilo(fig, 300, "Caídas en producción por duración", y="kWh", leyenda=False))

    tipos = st.multiselect("Tipos de episodio", list(t.index), default=list(t.index))
    ep = r.episodios[r.episodios["tipo"].isin(tipos)].sort_values("kWh", ascending=False)
    st.dataframe(ep[["tipo", "inicio", "fin", "horas", "kWh", "kW_medio", "estado_previo",
                     "estado_siguiente"]].round(1),
                 hide_index=True, use_container_width=True, height=280,
                 column_config={"inicio": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
                                "fin": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm")})

    st.subheader("Arranques después de paradas largas")
    st.caption(f"Paradas ≥ {p.min_parada_arranque_h:g} h; producción sostenida = "
               f"{p.intervalos_estable} intervalos seguidos ≥ {p.umbral_produccion_kw:g} kW.")
    a = r.arranques
    if len(a):
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = go.Figure()
            colores = [AZUL, NARANJA, AGUA, AMARILLO, VIOLETA]
            for k, (_, x) in enumerate(a.iterrows()):
                tramo = r.ei.loc[x["encendido"]: x["encendido"] + pd.Timedelta(hours=24), "kW_Total"]
                h = (tramo.index - x["encendido"]).total_seconds() / 3600
                fig.add_scatter(x=h, y=tramo.values, mode="lines",
                                name=f"{x['encendido']:%Y-%m-%d} ({x['horas_arranque']:.1f} h)",
                                line=dict(width=2, color=colores[k % len(colores)]))
            fig.add_hline(y=p.umbral_produccion_kw, line_dash="dash", line_color=GRIS)
            mostrar(estilo(fig, 320, "Potencia desde el encendido", y="kW", x="Horas desde el encendido"))
        with c2:
            st.dataframe(a.round(1), hide_index=True, use_container_width=True)
    else:
        st.info("No hay paradas largas seguidas de producción sostenida.")

    st.subheader("Sensibilidad al umbral de producción")
    s = r.sensibilidad
    fig = go.Figure(go.Scatter(x=s.index, y=s["%_energia_improductiva"], mode="lines+markers",
                               line=dict(color=NARANJA, width=2), marker=dict(size=9)))
    fig.add_vline(x=p.umbral_produccion_kw, line_dash="dash", line_color=GRIS)
    c1, c2 = st.columns([3, 2])
    with c1:
        mostrar(estilo(fig, 280, y="% energía improductiva", x="Umbral (kW)", leyenda=False))
    with c2:
        st.dataframe(s.round(2), use_container_width=True)

    st.download_button("Descargar resultados (Excel)", exportar_excel(r),
                       file_name=f"energia_{st.session_state['maquina']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
