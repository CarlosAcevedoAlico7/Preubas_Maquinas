import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import ESTADOS, H_INTERVALO, MAQUINAS
from ui.estado import rango, resultados
from ui.graficos import AZUL, COLOR_ESTADO, GRIS, estilo, mostrar, recortar


def render():
    r, rg = resultados(), rango()
    p = r.parametros
    maq = st.session_state["maquina"]
    st.title(f"Resumen energético — {maq}")
    st.caption(f"{MAQUINAS[maq]['nombre']} · SourceID {MAQUINAS[maq]['source_id']} · "
               f"rango {rg[0]:%d-%b-%Y} → {rg[1]:%d-%b-%Y}")

    ei = recortar(r.ei, rg)
    dias = max(ei.index.normalize().nunique(), 1)
    e_total = ei["energia_kWh"].sum()
    por_estado = ei.groupby("estado")["energia_kWh"].sum().reindex(ESTADOS).fillna(0)
    clasif = por_estado[["Producción", "Carga reducida", "Parada"]].sum()
    pct_imp = por_estado["Carga reducida"] / clasif * 100 if clasif else float("nan")
    kw_prod = ei.loc[ei["estado"] == "Producción", "kW_Total"].mean()
    kw_ref = r.mediana_ref.get("kW_medio_produccion")
    h_parada = (ei["estado"] == "Parada").sum() * H_INTERVALO
    h_prod_pct = (ei["estado"] == "Producción").mean() * 100

    ult = r.dia.index.max()
    al = r.alertas
    recientes = al[al["fin"] >= ult - pd.Timedelta(days=30)] if len(al) else al

    c = st.columns(3) + st.columns(3)
    c[0].metric("Energía consumida", f"{e_total / 1000:,.0f} MWh")
    c[1].metric("Promedio diario", f"{e_total / dias / 1000:,.2f} MWh/día")
    c[2].metric("kW medio en producción", f"{kw_prod:,.1f} kW",
                f"{kw_prod - kw_ref:+.1f} kW vs. base" if pd.notna(kw_ref) else None,
                delta_color="inverse", help="Equivale a kWh por hora producida (sección 7.4).")
    c[3].metric("Energía improductiva", f"{pct_imp:.2f} %",
                help=f"Energía en carga reducida ({p.umbral_parada_kw:g}–{p.umbral_produccion_kw:g} kW) "
                     "sobre la energía clasificada (sección 6).")
    c[4].metric("Tiempo en producción", f"{h_prod_pct:.1f} %", f"{h_parada:,.0f} h de parada",
                delta_color="off")
    c[5].metric("Alertas últimos 30 días", f"{len(recientes)}",
                f"{int((recientes['regla'] == 'Puntual').sum())} puntuales" if len(recientes) else None,
                delta_color="off")
    if p.tarifa_cop_kwh:
        st.info(f"Costo estimado de la energía improductiva en el rango: "
                f"**${por_estado['Carga reducida'] * p.tarifa_cop_kwh:,.0f} COP** "
                f"(tarifa {p.tarifa_cop_kwh:,.0f} COP/kWh).")

    # Energía mensual por estado
    meses = sorted(set(ei["mes"]))
    m = r.mensual_estados.loc[r.mensual_estados.index.isin(meses)]
    izq, der = st.columns([3, 2])
    with izq:
        fig = go.Figure()
        for est in ESTADOS:
            fig.add_bar(x=m.index, y=m[est] / 1000, name=est, marker_color=COLOR_ESTADO[est],
                        marker_line_width=0, hovertemplate="%{y:,.1f} MWh")
        fig.update_layout(barmode="stack")
        mostrar(estilo(fig, 360, "Energía mensual por estado operativo", y="MWh"))
    with der:
        fig = go.Figure(go.Bar(x=m.index, y=m["%_improductiva"], marker_color=COLOR_ESTADO["Carga reducida"],
                               hovertemplate="%{y:.2f} %", name="% improductiva"))
        mostrar(estilo(fig, 360, "% de energía improductiva por mes", y="%", leyenda=False))

    # Potencia diaria
    pdia = recortar(r.potencia_diaria, rg)
    fig = go.Figure()
    fig.add_scatter(x=pdia.index, y=pdia["max"], name="Máximo diario", mode="lines",
                    line=dict(color=GRIS, width=1))
    fig.add_scatter(x=pdia.index, y=pdia["mean"], name="Promedio diario", mode="lines",
                    line=dict(color=AZUL, width=2))
    mostrar(estilo(fig, 320, "Potencia total diaria (días con ≥ 50 % de datos)", y="kW"))

    st.subheader("Alertas más recientes")
    if len(al):
        t = al.sort_values("fin", ascending=False).head(8)
        st.dataframe(t[["inicio", "fin", "regla", "explicacion"]], hide_index=True,
                     use_container_width=True,
                     column_config={"inicio": st.column_config.DateColumn("Inicio"),
                                    "fin": st.column_config.DateColumn("Fin"),
                                    "regla": "Regla", "explicacion": "Explicación"})
    else:
        st.success("Sin alertas con los parámetros actuales.")
