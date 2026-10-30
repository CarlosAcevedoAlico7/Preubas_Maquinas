"""Paleta y utilidades de gráficas (Plotly) compartidas por todas las vistas."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Paleta categórica validada (orden fijo, nunca ciclado)
AZUL, NARANJA, AGUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
GRIS, GRIS_CLARO = "#898781", "#c3c2b7"
# Estados de alerta (reservados: solo para alertas, siempre con etiqueta)
CRITICO, ADVERTENCIA = "#d03b3b", "#fab219"

COLOR_ESTADO = {"Producción": AZUL, "Carga reducida": NARANJA,
                "Parada": GRIS, "Sin dato": GRIS_CLARO}
COLOR_PERIODO = {"Antes": AZUL, "Después": NARANJA, "Base": AZUL, "Reporte": NARANJA}
COLOR_FASE = {"A": AZUL, "B": NARANJA, "C": AGUA}
SECUENCIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def estilo(fig: go.Figure, alto: int = 360, titulo: str | None = None,
           y: str | None = None, x: str | None = None, leyenda: bool = True) -> go.Figure:
    fig.update_layout(
        height=alto,
        margin=dict(l=10, r=10, t=(34 if titulo else 0) + (30 if leyenda else 10), b=10),
        title=dict(text=titulo, x=0, xref="paper", y=1, yref="container", yanchor="top",
                   pad=dict(t=8), font=dict(size=14)) if titulo else None,
        hovermode="x unified", showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        bargap=0.15,
    )
    if y:
        fig.update_yaxes(title_text=y)
    if x is not None:
        fig.update_xaxes(title_text=x)
    return fig


def mostrar(fig: go.Figure):
    st.plotly_chart(fig, use_container_width=True, theme="streamlit",
                    config={"displaylogo": False, "locale": "es"})


def banda_transicion(fig: go.Figure, inicio, fin, **kw):
    fig.add_vrect(x0=inicio, x1=fin, fillcolor=GRIS, opacity=0.18, line_width=0,
                  annotation_text="Transición", annotation_position="top left", **kw)


def linea_vertical(fig: go.Figure, fecha, texto: str, color: str = GRIS, **kw):
    # add_vline con anotación falla con fechas en algunas versiones: se separan
    fig.add_vline(x=pd.Timestamp(fecha), line_dash="dash", line_color=color, line_width=1, **kw)
    fig.add_annotation(x=pd.Timestamp(fecha), y=1, yref="paper", text=texto, showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(size=11, color=color), **kw)


def recortar(obj, rango):
    """Filtra un DataFrame/Series con índice de fecha al rango de visualización."""
    if rango is None or obj is None or len(obj) == 0:
        return obj
    a, b = pd.Timestamp(rango[0]), pd.Timestamp(rango[1]) + pd.Timedelta(days=1)
    return obj[(obj.index >= a) & (obj.index < b)]
