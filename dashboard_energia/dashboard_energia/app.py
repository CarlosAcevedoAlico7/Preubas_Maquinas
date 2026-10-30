"""Dashboard energético — analítica de máquinas ALICO (inicia con EX14 VAREX II).

Ejecutar:  streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

from config import MAQUINAS, Parametros
from ui.estado import analizar, obtener_fuente, tipo_fuente
from vistas import (anomalias, calidad, consumo, desbalance, improductiva, linea_base,
                    resumen)

st.set_page_config(page_title="Dashboard energético", page_icon="⚡", layout="wide")


def d(s: str) -> date:
    return pd.Timestamp(s).date()


# ---------------------------------------------------------------------------
# Barra lateral: máquina, rango de visualización y parámetros del análisis
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ Gestión energética")
    maquina = st.selectbox("Máquina", list(MAQUINAS),
                           format_func=lambda k: f"{k} — {MAQUINAS[k]['nombre'].split('—')[0].strip()}")
    tipo = tipo_fuente()
    st.caption(f"Fuente: {obtener_fuente(tipo).descripcion(maquina)}")

    pdef = Parametros()
    with st.form("parametros"):
        with st.expander("Parámetros del análisis", expanded=False):
            st.markdown("**Estados operativos**")
            umbral = st.slider("Umbral de producción (kW)", 100, 230, int(pdef.umbral_produccion_kw), 5,
                               help="Proxy de 'en producción' (sección 5.2). Validar con datos de producción.")
            parada = st.number_input("Umbral de parada (kW)", 0.0, 20.0, pdef.umbral_parada_kw, 0.5)
            tarifa = st.number_input("Tarifa (COP/kWh, 0 = sin costo)", 0.0, 5000.0, 0.0, 10.0)
            st.markdown("**Filtro activo**")
            f_filtro = st.date_input("Inicio de transición", d(pdef.fecha_filtro))
            f_fin = st.date_input("Inicio del período 'Después'", d(pdef.fin_transicion))
            st.markdown("**Línea base**")
            base = st.date_input("Período base", (d(pdef.periodo_base[0]), d(pdef.periodo_base[1])))
            reporte = st.date_input("Período de reporte",
                                    (d(pdef.periodo_reporte[0]), d(pdef.periodo_reporte[1])))
            st.markdown("**Anomalías**")
            z_p = st.slider("|z| alerta puntual", 2.0, 6.0, pdef.z_puntual, 0.5)
            z_s = st.slider("|z| alerta sostenida (mediana 7 días)", 1.0, 4.0, pdef.z_sostenido, 0.25)
        st.form_submit_button("Recalcular", use_container_width=True)

    def _par(r, defecto):
        return tuple(str(x) for x in r) if isinstance(r, (tuple, list)) and len(r) == 2 else defecto

    params = Parametros(
        umbral_produccion_kw=float(umbral), umbral_parada_kw=float(parada),
        tarifa_cop_kwh=float(tarifa) or None,
        fecha_filtro=str(f_filtro), fin_transicion=str(f_fin),
        periodo_base=_par(base, pdef.periodo_base),
        periodo_reporte=_par(reporte, pdef.periodo_reporte),
        z_puntual=float(z_p), z_sostenido=float(z_s),
    )

try:
    r = analizar(tipo, maquina, params)
except FileNotFoundError as e:
    st.error(f"No se encontró la base de datos de {maquina}.\n\n{e}\n\n"
             "Revise `sqlite_dir` en `.streamlit/secrets.toml` o la ruta en `config.py`.")
    st.stop()
except Exception as e:  # conexión, credenciales, columnas
    st.error(f"No fue posible cargar los datos: {e}")
    st.stop()

st.session_state["resultados"] = r
st.session_state["maquina"] = maquina

with st.sidebar:
    ini, fin = r.limpio.index.min().date(), r.limpio.index.max().date()
    rng = st.date_input("Rango de visualización", (ini, fin), min_value=ini, max_value=fin,
                        help="Filtra las gráficas temporales. Los cálculos usan siempre todo el histórico.")
    st.session_state["rango"] = rng if isinstance(rng, (tuple, list)) and len(rng) == 2 else (ini, fin)
    st.caption(f"Datos: {ini:%d-%b-%Y} → {fin:%d-%b-%Y}")

paginas = [
    st.Page(resumen.render, title="Resumen", icon="📊", url_path="resumen", default=True),
    st.Page(consumo.render, title="Consumo y operación", icon="🔌", url_path="consumo"),
    st.Page(improductiva.render, title="Energía improductiva", icon="⏳", url_path="improductiva"),
    st.Page(linea_base.render, title="Línea base y CUSUM", icon="📈", url_path="linea-base"),
    st.Page(desbalance.render, title="Fases y desbalance", icon="⚖️", url_path="desbalance"),
    st.Page(anomalias.render, title="Anomalías", icon="🚨", url_path="anomalias"),
    st.Page(calidad.render, title="Calidad de datos", icon="🧪", url_path="calidad"),
]
st.navigation(paginas).run()
