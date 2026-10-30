"""Capa de acceso a datos.

Toda la analítica consume un DataFrame con las columnas canónicas de config.py, sin importar
de dónde venga. Cambiar de SQLite a Snowflake es cuestión de configuración (secrets.toml o
variable de entorno FUENTE_DATOS), no de código.

    tipo = "sqlite"     -> FuenteSQLite   (copia local, solo lectura)
    tipo = "snowflake"  -> FuenteSnowflake (st.connection o snowflake-connector-python)
"""
from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from config import COL_FECHA, COLS_NUM, MAQUINAS

COLUMNAS_CANONICAS = [COL_FECHA] + COLS_NUM


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas a los nombres canónicos sin distinguir mayúsculas.

    Snowflake devuelve en MAYÚSCULAS los identificadores sin comillas (FECHAHORA, KW_FASEA...),
    así que se mapea por nombre en minúsculas.
    """
    mapa = {c.lower(): c for c in COLUMNAS_CANONICAS}
    df = df.rename(columns={c: mapa.get(str(c).lower(), c) for c in df.columns})
    faltan = [c for c in COLUMNAS_CANONICAS if c not in df.columns]
    if faltan:
        raise ValueError(f"La fuente no tiene las columnas esperadas: {faltan}")
    return df[COLUMNAS_CANONICAS]


class FuenteDatos(ABC):
    nombre: str = ""

    @abstractmethod
    def leer_mediciones(self, maquina: str) -> pd.DataFrame:
        """Devuelve las mediciones crudas de la máquina con columnas canónicas."""

    def descripcion(self, maquina: str) -> str:
        return self.nombre


class FuenteSQLite(FuenteDatos):
    nombre = "SQLite (local)"

    def __init__(self, directorio: str | Path = "."):
        self.directorio = Path(directorio)

    def _ruta(self, maquina: str) -> Path:
        ruta = Path(MAQUINAS[maquina]["sqlite_ruta"])
        return ruta if ruta.is_absolute() else self.directorio / ruta

    def leer_mediciones(self, maquina: str) -> pd.DataFrame:
        ruta = self._ruta(maquina)
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró la base {ruta.resolve()}")
        tabla = MAQUINAS[maquina]["sqlite_tabla"]
        # Solo lectura: el dashboard nunca modifica la copia local
        con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{tabla}"', con)
        finally:
            con.close()
        return normalizar_columnas(df)

    def descripcion(self, maquina: str) -> str:
        return f"SQLite · {self._ruta(maquina).name} · {MAQUINAS[maquina]['sqlite_tabla']}"


class FuenteSnowflake(FuenteDatos):
    """Lectura desde Snowflake.

    Usa st.connection("snowflake") si se ejecuta dentro de Streamlit (credenciales en
    .streamlit/secrets.toml, sección [connections.snowflake]). Fuera de Streamlit usa
    snowflake-connector-python con los parámetros recibidos.
    """
    nombre = "Snowflake"

    def __init__(self, parametros_conexion: dict | None = None):
        self.parametros_conexion = parametros_conexion or {}

    def _consulta(self, maquina: str) -> str:
        cfg = MAQUINAS[maquina]
        sql = f"SELECT * FROM {cfg['snowflake_tabla']}"
        if cfg.get("snowflake_filtro"):
            sql += f" WHERE {cfg['snowflake_filtro']}"
        return sql

    def leer_mediciones(self, maquina: str) -> pd.DataFrame:
        sql = self._consulta(maquina)
        try:
            import streamlit as st
            if st.runtime.exists():
                df = st.connection("snowflake").query(sql, ttl=0)
                return normalizar_columnas(df)
        except ImportError:
            pass
        import snowflake.connector  # pip install snowflake-connector-python[pandas]
        with snowflake.connector.connect(**self.parametros_conexion) as con:
            df = con.cursor().execute(sql).fetch_pandas_all()
        return normalizar_columnas(df)

    def descripcion(self, maquina: str) -> str:
        return f"Snowflake · {MAQUINAS[maquina]['snowflake_tabla']}"


def crear_fuente(config: dict | None = None) -> FuenteDatos:
    """Crea la fuente según configuración.

    Prioridad: variable de entorno FUENTE_DATOS > config["tipo"] > "sqlite".
    config proviene de la sección [fuente] de secrets.toml.
    """
    config = dict(config or {})
    tipo = os.environ.get("FUENTE_DATOS", config.get("tipo", "sqlite")).lower()
    if tipo == "sqlite":
        directorio = os.environ.get("SQLITE_DIR", config.get("sqlite_dir", "."))
        return FuenteSQLite(directorio)
    if tipo == "snowflake":
        return FuenteSnowflake(config.get("snowflake"))
    raise ValueError(f"Tipo de fuente no soportado: {tipo!r} (use 'sqlite' o 'snowflake')")
