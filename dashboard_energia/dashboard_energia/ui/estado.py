"""Carga cacheada de datos y resultados, y acceso al estado compartido entre páginas."""
from __future__ import annotations

import os

import streamlit as st

from analitica import Resultados, ejecutar
from config import Parametros
from datos import crear_fuente


def config_fuente() -> dict:
    """Lee la sección [fuente] de .streamlit/secrets.toml (si existe)."""
    try:
        return dict(st.secrets.get("fuente", {}))
    except Exception:  # sin secrets.toml
        return {}


@st.cache_resource
def obtener_fuente(tipo: str):
    cfg = config_fuente()
    cfg["tipo"] = tipo
    return crear_fuente(cfg)


def tipo_fuente() -> str:
    return os.environ.get("FUENTE_DATOS", config_fuente().get("tipo", "sqlite")).lower()


@st.cache_data(ttl=3600, show_spinner="Leyendo mediciones…")
def cargar_crudo(tipo: str, maquina: str):
    return obtener_fuente(tipo).leer_mediciones(maquina)


@st.cache_data(ttl=3600, show_spinner="Calculando indicadores…", max_entries=8)
def analizar(tipo: str, maquina: str, p: Parametros) -> Resultados:
    return ejecutar(cargar_crudo(tipo, maquina), p)


def resultados() -> Resultados:
    return st.session_state["resultados"]


def rango() -> tuple:
    return st.session_state.get("rango")
