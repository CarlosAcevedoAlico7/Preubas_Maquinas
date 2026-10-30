import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from analitica.anomalias import NOMBRES
from ui.estado import rango, resultados
from ui.graficos import AGUA, AZUL, CRITICO, ADVERTENCIA, estilo, mostrar, recortar


def render():
    r, rg = resultados(), rango()
    p = r.parametros
    al = r.alertas
    st.title("Detección de anomalías")
    st.caption(f"z robusto respecto al período base ({p.periodo_base[0]} → {p.periodo_base[1]}). "
               f"Puntual: |z| ≥ {p.z_puntual:g} en un día. Sostenida: mediana de z en "
               f"{p.dias_sostenido} días con |z| ≥ {p.z_sostenido:g} (solo días pasados, como en operación).")

    c = st.columns(4)
    c[0].metric("Alertas puntuales", int((al["regla"] == "Puntual").sum()) if len(al) else 0)
    c[1].metric("Episodios sostenidos", int((al["regla"] == "Sostenida").sum()) if len(al) else 0)
    en_base = al[(al["inicio"] >= p.periodo_base[0]) & (al["inicio"] <= p.periodo_base[1])] if len(al) else al
    c[2].metric("Alertas en el período base", len(en_base),
                help="Muchas alertas en el período base indican umbrales demasiado sensibles.")
    ult = r.dia.index.max()
    activas = al[al["fin"] >= ult - pd.Timedelta(days=1)] if len(al) else al
    c[3].metric("Activas al último día", len(activas))

    # Panel de seguimiento
    cols = list(r.indicadores.columns)
    elegidos = st.multiselect("Indicadores", cols, default=cols,
                              format_func=lambda c: NOMBRES[c][0])
    ind = recortar(r.indicadores, rg)
    if elegidos:
        fig = make_subplots(rows=len(elegidos), cols=1, shared_xaxes=True, vertical_spacing=0.03,
                            subplot_titles=[f"{NOMBRES[c][0]} ({NOMBRES[c][1]})" if NOMBRES[c][1]
                                            else NOMBRES[c][0] for c in elegidos])
        for i, col in enumerate(elegidos, start=1):
            med, esc = r.mediana_ref[col], r.escala_ref[col]
            fig.add_hrect(y0=med - 3 * esc, y1=med + 3 * esc, fillcolor=AGUA, opacity=0.12,
                          line_width=0, row=i, col=1)
            fig.add_scatter(x=ind.index, y=ind[col], mode="lines", line=dict(color=AZUL, width=1.2),
                            name=NOMBRES[col][0], showlegend=False, row=i, col=1)
            a = al[al["indicador"] == col] if len(al) else al
            for _, x in a[a["regla"] == "Sostenida"].iterrows():
                fig.add_vrect(x0=x["inicio"], x1=x["fin"] + pd.Timedelta(days=1), fillcolor=ADVERTENCIA,
                              opacity=0.25, line_width=0, row=i, col=1)
            pu = a[a["regla"] == "Puntual"]
            if len(pu):
                fig.add_scatter(x=pu["inicio"], y=pu["valor"], mode="markers", showlegend=False,
                                marker=dict(size=9, color=CRITICO, symbol="x"),
                                name="Alerta puntual", row=i, col=1)
        for a_ in fig.layout.annotations:
            if a_.xref == "paper":
                a_.update(x=0, xanchor="left", font=dict(size=12))
        mostrar(estilo(fig, 170 * len(elegidos) + 40, leyenda=False))
        st.caption("Franja verde: rango normal (mediana ± 3 dispersiones robustas del período base) · "
                   "sombreado amarillo: alerta sostenida · ✕ roja: alerta puntual.")

    st.subheader("Listado de alertas")
    if not len(al):
        st.success("Sin alertas con los parámetros actuales.")
        return
    f1, f2, f3 = st.columns(3)
    reglas = f1.multiselect("Regla", ["Puntual", "Sostenida"], default=["Puntual", "Sostenida"])
    inds = f2.multiselect("Indicador", sorted(al["indicador"].unique()),
                          format_func=lambda c: NOMBRES[c][0])
    sin_parada = f3.toggle("Ocultar alertas con días de parada", value=False)
    t = al[al["regla"].isin(reglas)]
    if inds:
        t = t[t["indicador"].isin(inds)]
    if sin_parada:
        t = t[~t["con_parada"]]
    st.dataframe(t[["inicio", "fin", "regla", "indicador", "z", "dias", "explicacion"]]
                 .sort_values("inicio", ascending=False).round({"z": 1}),
                 hide_index=True, use_container_width=True,
                 column_config={"inicio": st.column_config.DateColumn("Inicio"),
                                "fin": st.column_config.DateColumn("Fin"),
                                "indicador": st.column_config.TextColumn("Indicador"),
                                "explicacion": st.column_config.TextColumn("Explicación", width="large")})
    st.download_button("Descargar alertas (CSV)", t.to_csv(index=False, date_format="%Y-%m-%d"),
                       file_name=f"alertas_{st.session_state['maquina']}.csv", mime="text/csv")

    with st.expander("Referencia del período base"):
        st.dataframe(pd.DataFrame({"mediana_base": r.mediana_ref, "dispersión_robusta": r.escala_ref})
                     .rename(index=lambda c: NOMBRES[c][0]).round(3), use_container_width=True)
