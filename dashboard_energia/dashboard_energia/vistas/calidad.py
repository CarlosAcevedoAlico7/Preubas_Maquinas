import plotly.graph_objects as go
import streamlit as st

from ui.estado import resultados
from ui.graficos import estilo, mostrar

ROJOS = ["#fcfcfb", "#f6c9c4", "#ee9a92", "#e34948", "#b02e2e", "#7a1d1d"]


def render():
    r = resultados()
    st.title("Calidad de datos")
    d = r.diagnostico
    rl = r.resumen_limpieza
    c = st.columns(5)
    c[0].metric("Registros originales", f"{d['registros']:,}")
    c[1].metric("Puntos de grilla 15 min", f"{rl['Puntos de la grilla de 15 min']:,}")
    c[2].metric("Sin registro", f"{rl['Puntos sin registro']:,}")
    c[3].metric("Cobertura kW_Total", f"{rl['Cobertura kW_Total (%)']:.1f} %")
    c[4].metric("Cobertura contador kWh", f"{rl['Cobertura kWh_intervalo (%)']:.1f} %")
    st.caption(f"Intervalo mediano {d['intervalo_mediano']} ({d['pct_intervalo_mediano']:.1f} % de los intervalos) · "
               f"{d['fuera_grilla']} registros fuera de la grilla · {d['duplicados']} filas duplicadas · "
               f"{d['marcas_repetidas']} marcas repetidas.")

    f = r.faltantes_mes
    fig = go.Figure(go.Heatmap(z=f.T.values, x=list(f.index), y=list(f.columns), zmin=0, zmax=100,
                               colorscale=[[i / (len(ROJOS) - 1), c] for i, c in enumerate(ROJOS)],
                               colorbar=dict(title="% faltante"),
                               hovertemplate="%{y} · %{x}: %{z:.1f} %<extra></extra>"))
    estilo(fig, 280, "Porcentaje de faltantes por mes y variable", leyenda=False)
    fig.update_layout(hovermode="closest")
    mostrar(fig)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Huecos sin registro")
        st.dataframe(d["huecos"].round(2), hide_index=True, use_container_width=True)
        st.subheader("Faltantes por variable")
        st.dataframe(r.resumen_tipos.round(2), use_container_width=True)
    with c2:
        st.subheader("Coherencia física y unidades")
        st.dataframe(r.chequeos.round(3).to_frame(), use_container_width=True)
        st.caption("Esperado: V_LL/V_LN ≈ 1,732; suma de fases = kW_Demanda (razón y correlación 1); "
                   "contador sin incrementos negativos; energía integrada / contador ≈ 1.")
        st.subheader("Construcción del dataset")
        st.dataframe({k: round(v, 1) if isinstance(v, float) else v for k, v in rl.items()},
                     use_container_width=True)
        ie = r.energia_info
        st.caption(f"Energía del contador {ie['energia_contador']:,.0f} kWh · asignada a estados "
                   f"{ie['energia_asignada']:,.0f} kWh · no asignada {ie['energia_no_asignada']:,.0f} kWh "
                   "(bordes de huecos).")
