"""Orquesta todo el análisis del notebook sobre los datos crudos de una máquina.

No depende de Streamlit: se puede usar en scripts, en otro notebook o en una tarea programada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd

from config import Parametros
from . import anomalias, desbalance, eda, improductiva, limpieza, linea_base


@dataclass
class Resultados:
    # 3–4
    df: pd.DataFrame
    resumen_tipos: pd.DataFrame
    diagnostico: dict
    faltantes_mes: pd.DataFrame
    chequeos: pd.Series
    limpio: pd.DataFrame
    resumen_limpieza: dict
    # 5
    potencia_diaria: pd.DataFrame
    percentiles: pd.Series
    energia_mes: pd.DataFrame
    fases: pd.DataFrame
    eventos_v: pd.DataFrame
    v_ref: pd.Series
    paradas: pd.DataFrame
    # 5.6
    op: pd.DataFrame
    periodos: pd.DataFrame
    desb_diario: pd.DataFrame
    saltos: pd.DataFrame
    fecha_cambio: pd.Timestamp | None
    comparacion: pd.DataFrame
    p95: pd.DataFrame
    por_banda: pd.DataFrame
    reparto: pd.DataFrame
    fp: pd.DataFrame
    # 6
    ei: pd.DataFrame
    energia_info: dict
    balance: pd.DataFrame
    pct_improductiva: float
    mensual_estados: pd.DataFrame
    horas_mes: pd.DataFrame
    episodios: pd.DataFrame
    tipos_episodio: pd.DataFrame
    duracion_caidas: pd.DataFrame
    arranques: pd.DataFrame
    sensibilidad: pd.DataFrame
    # 7
    dia: pd.DataFrame
    lb: dict
    kw_prod: pd.DataFrame
    banda_kw_prod: tuple
    # 8
    indicadores: pd.DataFrame
    mediana_ref: pd.Series
    escala_ref: pd.Series
    z: pd.DataFrame
    alertas: pd.DataFrame
    parametros: Parametros = field(default_factory=Parametros)


def ejecutar(raw: pd.DataFrame, p: Parametros) -> Resultados:
    df, resumen_tipos = limpieza.convertir_tipos(raw)
    diag = limpieza.diagnostico_registros(df)
    falt = limpieza.faltantes_por_mes(df)
    cheq = limpieza.chequeos_fisicos(df)
    limpio, res_limp = limpieza.construir_dataset(df)

    eventos_v, v_ref = eda.eventos_voltaje(limpio, p)

    op = desbalance.intervalos_produccion(limpio, p)
    d_diario = desbalance.desbalance_diario(op)
    saltos, fecha_cambio = desbalance.detectar_cambio(d_diario, p)
    comp, p95 = desbalance.comparar_periodos(op)
    reparto, fp = desbalance.reparto_y_fp(op)

    ei, info = improductiva.tabla_estados(limpio, p)
    balance, pct = improductiva.balance_estados(ei, p)
    mensual, horas_mes = improductiva.mensual_estados(ei)
    bloques = improductiva.bloques_estado(ei)
    episodios, tipos = improductiva.episodios_carga_reducida(bloques)

    dia = linea_base.tabla_diaria(ei, p)
    lb = linea_base.modelo_linea_base(dia)
    kw_prod, banda = linea_base.indicador_kw_produccion(ei, dia, p)

    ind = anomalias.indicadores_diarios(limpio, ei, dia, lb.get("validos"), p)
    med, esc, z = anomalias.referencia(ind, p)
    alertas = anomalias.generar_alertas(ind, z, med, dia, p)

    return Resultados(
        df=df, resumen_tipos=resumen_tipos, diagnostico=diag, faltantes_mes=falt,
        chequeos=cheq, limpio=limpio, resumen_limpieza=res_limp,
        potencia_diaria=eda.potencia_diaria(limpio), percentiles=eda.percentiles_potencia(limpio),
        energia_mes=eda.energia_mensual(limpio), fases=eda.resumen_fases(limpio),
        eventos_v=eventos_v, v_ref=v_ref, paradas=eda.bloques_potencia_cero(limpio),
        op=op, periodos=desbalance.tabla_periodos(op), desb_diario=d_diario, saltos=saltos,
        fecha_cambio=fecha_cambio, comparacion=comp, p95=p95,
        por_banda=desbalance.desbalance_por_banda(op, p), reparto=reparto, fp=fp,
        ei=ei, energia_info=info, balance=balance, pct_improductiva=pct,
        mensual_estados=mensual, horas_mes=horas_mes, episodios=episodios,
        tipos_episodio=tipos, duracion_caidas=improductiva.duracion_caidas(episodios),
        arranques=improductiva.arranques(ei, bloques, p),
        sensibilidad=improductiva.sensibilidad_umbral(ei, p),
        dia=dia, lb=lb, kw_prod=kw_prod, banda_kw_prod=banda,
        indicadores=ind, mediana_ref=med, escala_ref=esc, z=z, alertas=alertas, parametros=p,
    )


def exportar_excel(r: Resultados) -> bytes:
    """Equivalente a las exportaciones 6.7 y 8 del notebook, en un solo libro."""
    buf = BytesIO()
    with pd.ExcelWriter(buf) as w:
        r.balance.to_excel(w, sheet_name="balance_estados")
        pd.concat({"kWh": r.mensual_estados, "horas": r.horas_mes}, axis=1).to_excel(
            w, sheet_name="mensual_estados")
        r.tipos_episodio.to_excel(w, sheet_name="tipos_episodio")
        r.episodios.to_excel(w, sheet_name="episodios")
        r.arranques.to_excel(w, sheet_name="arranques", index=False)
        r.sensibilidad.to_excel(w, sheet_name="sensibilidad")
        r.energia_mes.to_excel(w, sheet_name="energia_mensual")
        r.comparacion.to_excel(w, sheet_name="desbalance_antes_despues")
        if r.lb:
            r.lb["mensual"].to_excel(w, sheet_name="linea_base_mensual")
        r.alertas.to_excel(w, sheet_name="alertas", index=False)
    return buf.getvalue()
