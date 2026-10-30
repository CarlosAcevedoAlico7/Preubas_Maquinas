"""Configuración del dashboard: máquinas, columnas y parámetros por defecto.

Para agregar una máquina (BO3, FL21, Totani...) basta con añadir una entrada a MAQUINAS.
Los parámetros analíticos por defecto replican los del notebook analisis_varex14 v0.6 y se
pueden ajustar desde la barra lateral del dashboard.
"""
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Máquinas disponibles
# ---------------------------------------------------------------------------
# - sqlite_ruta / sqlite_tabla: copia local actual.
# - snowflake_tabla / snowflake_filtro: destino de la migración. Si en Snowflake todas las
#   máquinas quedan en una sola tabla, usar snowflake_filtro (p. ej. "SOURCEID = 319").
MAQUINAS = {
    "EX14": {
        "nombre": "EX14 VAREX II — Windmöller & Hölscher",
        "source_id": 319,
        "sqlite_ruta": "EX14_VAREX_II.sqlite",
        "sqlite_tabla": "Datos_varex_14",
        "snowflake_tabla": "DATOS_VAREX_14",
        "snowflake_filtro": None,
    },
}

# ---------------------------------------------------------------------------
# Columnas canónicas (nombres usados por toda la analítica)
# ---------------------------------------------------------------------------
COL_FECHA = "FechaHora"
COLS_V = ["V_AN", "V_BN", "V_CN", "V_LL_Prom", "V_LN_Prom"]
COLS_I = ["I_A", "I_B", "I_C", "I_Prom"]
COLS_KW = ["kW_Demanda", "kW_FaseA", "kW_FaseB", "kW_FaseC"]
COLS_NUM = COLS_V + COLS_I + COLS_KW + ["kWh_Acumulado"]
FASES_I = ["I_A", "I_B", "I_C"]
FASES_V = ["V_AN", "V_BN", "V_CN"]
FASES_KW = ["kW_FaseA", "kW_FaseB", "kW_FaseC"]
FASES_FP = ["FP_A", "FP_B", "FP_C"]

FREQ = "15min"
H_INTERVALO = 0.25
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

ESTADOS = ["Producción", "Carga reducida", "Parada", "Sin dato"]


@dataclass(frozen=True)
class Parametros:
    """Parámetros analíticos. Frozen + hashable para que st.cache_data los use como clave."""
    # Estados operativos (secciones 5.2 y 6)
    umbral_produccion_kw: float = 180.0
    umbral_parada_kw: float = 1.0
    min_parada_arranque_h: float = 4.0
    intervalos_estable: int = 4
    tarifa_cop_kwh: float | None = None
    # Filtro activo (5.6)
    fecha_filtro: str = "2025-12-01"
    fin_transicion: str = "2026-01-01"
    ventana_busqueda: tuple = ("2025-10-01", "2026-03-01")
    dias_ventana: int = 30
    # Línea base (7)
    periodo_base: tuple = ("2025-01-01", "2025-10-31")
    periodo_reporte: tuple = ("2025-11-01", "2026-10-21")
    cobertura_min: float = 0.95
    # Anomalías (8)
    z_puntual: float = 3.5
    z_sostenido: float = 2.0
    dias_sostenido: int = 7
    min_intervalos_prod: int = 24
    # Eventos de voltaje (5.7)
    desv_voltaje: float = 0.10
