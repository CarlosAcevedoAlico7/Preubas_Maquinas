import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DIAS, FASES_KW, FASES_V
from ui.estado import rango, resultados
from ui.graficos import (AGUA, AZUL, COLOR_FASE, GRIS, NARANJA, SECUENCIAL, estilo, mostrar,
                         recortar)


def render():
    r, rg = resultados(), rango()
    p = r.parametros
    st.title("Consumo y operación")

    # --- Serie de 15 min ----------------------------------------------------
    st.subheader("Detalle de 15 minutos")
    fin = pd.Timestamp(rg[1])
    sel = st.date_input("Ventana (máx. 31 días)", (fin - pd.Timedelta(days=6), fin),
                        min_value=r.limpio.index.min().date(), max_value=r.limpio.index.max().date(),
                        key="ventana_15min")
    if isinstance(sel, (tuple, list)) and len(sel) == 2:
        a, b = pd.Timestamp(sel[0]), min(pd.Timestamp(sel[1]), pd.Timestamp(sel[0]) + pd.Timedelta(days=30))
        tramo = r.limpio.loc[a: b + pd.Timedelta(days=1) - pd.Timedelta("15min")]
        ver_fases = st.toggle("Mostrar potencia por fase", value=False)
        fig = go.Figure()
        if ver_fases:
            for col, f in zip(FASES_KW, "ABC"):
                fig.add_scatter(x=tramo.index, y=tramo[col], name=f"Fase {f}", mode="lines",
                                line=dict(color=COLOR_FASE[f], width=1.5))
        else:
            fig.add_scatter(x=tramo.index, y=tramo["kW_Total"], name="kW_Total", mode="lines",
                            line=dict(color=AZUL, width=1.5))
            fig.add_hline(y=p.umbral_produccion_kw, line_dash="dash", line_color=GRIS,
                          annotation_text=f"Umbral de producción {p.umbral_produccion_kw:g} kW",
                          annotation_position="bottom right")
        mostrar(estilo(fig, 320, y="kW"))

    # --- Distribución y perfil ---------------------------------------------
    izq, der = st.columns(2)
    lim = recortar(r.limpio, rg)
    with izq:
        log = st.toggle("Escala logarítmica en frecuencia", value=True)
        kw = lim["kW_Total"].dropna()
        fig = go.Figure(go.Histogram(x=kw, nbinsx=120, marker_color=AZUL, marker_line_width=0,
                                     name="Intervalos"))
        fig.add_vline(x=p.umbral_produccion_kw, line_dash="dash", line_color=NARANJA)
        if log:
            fig.update_yaxes(type="log")
        estilo(fig, 340, "Distribución de kW_Total (estados operativos)", y="Intervalos",
               x="kW", leyenda=False)
        fig.update_layout(hovermode="closest")
        mostrar(fig)
        pc = kw.describe(percentiles=[.05, .25, .5, .75, .95, .99])
        st.caption(f"Mediana {pc['50%']:.0f} kW · P25–P75 {pc['25%']:.0f}–{pc['75%']:.0f} kW · "
                   f"P99 {pc['99%']:.0f} kW · máx {pc['max']:.0f} kW · "
                   f"{(kw == 0).sum():,} intervalos en cero")
    with der:
        solo = st.toggle(f"Solo intervalos en producción (≥ {p.umbral_produccion_kw:g} kW)",
                         value=False)
        d = lim[lim["kW_Total"] >= p.umbral_produccion_kw] if solo else lim
        perfil = d.pivot_table(index="dia_semana", columns="hora", values="kW_Total",
                               aggfunc="mean").reindex(range(7))
        fig = go.Figure(go.Heatmap(z=perfil.values, x=list(perfil.columns), y=DIAS,
                                   colorscale=SECUENCIAL, colorbar=dict(title="kW"),
                                   hovertemplate="%{y} %{x}:00 · %{z:.1f} kW<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        estilo(fig, 340, "kW_Total promedio por día de la semana y hora", x="Hora del día",
               leyenda=False)
        fig.update_layout(hovermode="closest")
        mostrar(fig)

    # --- Energía mensual -----------------------------------------------------
    st.subheader("Energía mensual (contador kWh_Acumulado)")
    em = r.energia_mes.copy()
    em["MWh"] = em["kWh"] / 1000
    em["MWh_por_dia"] = em["MWh"] / em["dias"]
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Bar(x=em.index, y=em["MWh_por_dia"], marker_color=AZUL,
                               customdata=em[["MWh", "cobertura_pct"]],
                               hovertemplate="%{y:.2f} MWh/día<br>%{customdata[0]:,.1f} MWh en el mes"
                                             "<br>cobertura %{customdata[1]:.1f} %<extra></extra>"))
        mostrar(estilo(fig, 320, "Energía promedio por día de cada mes (normaliza meses parciales)",
                       y="MWh/día", leyenda=False))
    with c2:
        st.dataframe(em[["MWh", "MWh_por_dia", "cobertura_pct", "horas_potencia_cero"]],
                     use_container_width=True, height=320,
                     column_config={"MWh": st.column_config.NumberColumn("MWh", format="%.1f"),
                                    "MWh_por_dia": st.column_config.NumberColumn("MWh/día", format="%.2f"),
                                    "cobertura_pct": st.column_config.NumberColumn("Cobertura %", format="%.1f"),
                                    "horas_potencia_cero": st.column_config.NumberColumn("h en cero", format="%.1f")})

    # --- Paradas y eventos de voltaje ----------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Bloques con potencia cero")
        par = r.paradas
        st.caption(f"{len(par)} bloques · {par['horas'].sum():,.1f} h en total")
        st.dataframe(par, hide_index=True, use_container_width=True,
                     column_config={"inicio": st.column_config.DatetimeColumn("Inicio", format="YYYY-MM-DD HH:mm"),
                                    "fin": st.column_config.DatetimeColumn("Fin", format="YYYY-MM-DD HH:mm"),
                                    "horas": st.column_config.NumberColumn("Horas", format="%.2f")})
    with c2:
        st.subheader("Eventos de voltaje")
        st.caption(f"Alguna fase fuera de ±{p.desv_voltaje:.0%} de su mediana "
                   f"({', '.join(f'{k} {v:.1f} V' for k, v in r.v_ref.items())}). "
                   "Umbral exploratorio; con promedios de 15 min los huecos cortos no se ven.")
        if len(r.eventos_v):
            st.dataframe(r.eventos_v.round(2), use_container_width=True)
        else:
            st.success("Sin eventos.")
        vmin = recortar(r.limpio[FASES_V].min(axis=1).resample("D").min(), rg)
        fig = go.Figure(go.Scatter(x=vmin.index, y=vmin, mode="lines", line=dict(color=AGUA, width=1.5),
                                   name="V mínimo de fase"))
        mostrar(estilo(fig, 220, "Voltaje mínimo de fase por día", y="V", leyenda=False))
