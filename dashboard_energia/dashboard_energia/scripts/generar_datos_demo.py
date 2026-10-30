"""Genera una base SQLite SINTÉTICA con la misma estructura que EX14_VAREX_II.sqlite.

Sirve para probar el dashboard sin la base real. Reproduce los rasgos que documenta el
notebook (NULL como texto, registros desfasados ±1 s, huecos de fin de año, bloques sin
variables instantáneas, kW_Demanda ausente en may–ago 2025, cambio de reparto de carga en
nov-2025, evento de voltaje el 25-ago-2026), pero los valores NO son reales.

Uso:  python scripts/generar_datos_demo.py [ruta_salida]
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SALIDA = Path(sys.argv[1] if len(sys.argv) > 1 else "demo/EX14_VAREX_II.sqlite")
rng = np.random.default_rng(14)

idx = pd.date_range("2024-10-22 13:45", "2026-10-22 13:30", freq="15min")
n = len(idx)

# Potencia total: producción ~240 kW con ruido autocorrelado
ruido = pd.Series(rng.standard_normal(n)).rolling(8, min_periods=1).mean().to_numpy()
kw = 241 + 25 * ruido + 6 * np.sin(2 * np.pi * idx.dayofyear / 365)
kw = pd.Series(kw, index=idx)

def tramo(a, b):
    return (idx >= pd.Timestamp(a)) & (idx < pd.Timestamp(b))

# Caídas en producción cortas (~230)
for t in rng.choice(n - 40, 230, replace=False):
    dur = int(rng.choice([1, 2, 2, 3, 4, 4, 6, 8, 12, 20, 50]))
    kw.iloc[t:t + dur] = rng.uniform(40, 170, dur)

# Episodio de baja carga y paradas
kw[tramo("2024-11-17 02:15", "2024-11-26 08:45")] = rng.uniform(5, 50, tramo("2024-11-17 02:15", "2024-11-26 08:45").sum())
paradas = [("2024-11-26 08:45", "2024-11-26 15:00"), ("2024-12-27 16:45", "2025-01-02 16:45"),
           ("2025-04-17 05:00", "2025-04-20 17:15"), ("2025-12-26 15:15", "2026-01-02 05:15"),
           ("2026-08-25 10:15", "2026-08-25 10:30")]
for a, b in paradas:
    m = tramo(a, b)
    kw[m] = 0.0
    # rampa de arranque después de paradas largas
    fin = pd.Timestamp(b)
    if (fin - pd.Timestamp(a)).total_seconds() > 4 * 3600:
        r = tramo(fin, fin + pd.Timedelta(hours=14))
        kw[r] = np.linspace(20, 175, r.sum()) + rng.normal(0, 8, r.sum())
kw = kw.clip(lower=0)

# Reparto entre fases: cambio el 11-nov-2025 (fase C pierde carga)
despues = idx >= pd.Timestamp("2025-11-11")
sa = np.where(despues, 0.339, 0.327) + rng.normal(0, 0.004, n)
sb = np.where(despues, 0.362, 0.350) + rng.normal(0, 0.004, n)
sc = 1 - sa - sb
kwA, kwB, kwC = kw * sa, kw * sb, kw * sc

vA = 235.1 + rng.normal(0, 1.2, n); vB = 235.3 + rng.normal(0, 1.2, n); vC = 233.5 + rng.normal(0, 1.2, n)
ev = idx == pd.Timestamp("2026-08-25 09:15")
vA[ev], vB[ev] = 115.07, 117.43
fpA = np.where(despues, 0.90, 0.95); fpB = np.where(despues, 0.95, 0.96); fpC = np.where(despues, 0.94, 0.96)
iA = kwA * 1000 / (vA * fpA); iB = kwB * 1000 / (vB * fpB); iC = kwC * 1000 / (vC * fpC)

kwh = 1_250_000 + np.concatenate([[0], np.cumsum(kw.to_numpy()[:-1] * 0.25)])

df = pd.DataFrame({
    "FechaHora": idx, "V_AN": vA, "V_BN": vB, "V_CN": vC,
    "V_LL_Prom": np.sqrt(3) * (vA + vB + vC) / 3, "V_LN_Prom": (vA + vB + vC) / 3,
    "I_A": iA, "I_B": iB, "I_C": iC, "I_Prom": (iA + iB + iC) / 3,
    "kW_Demanda": kwA + kwB + kwC, "kW_FaseA": kwA, "kW_FaseB": kwB, "kW_FaseC": kwC,
    "kWh_Acumulado": kwh,
}).reset_index(drop=True)
num = df.columns.drop("FechaHora")
df[num] = df[num].astype(float).round(2)
df.loc[ev, ["kW_Demanda", "kW_FaseA", "kW_FaseB", "kW_FaseC"]] = np.nan

inst = [c for c in df.columns if c not in ("FechaHora", "kWh_Acumulado")]
for a, b in [("2024-11-05", "2024-11-14 12:00"), ("2026-10-09", "2026-10-18 12:00"),
             ("2025-10-03", "2025-10-04"), ("2026-06-10", "2026-06-11")]:
    df.loc[tramo(a, b), inst] = np.nan
df.loc[tramo("2025-05-08", "2025-08-25"), "kW_Demanda"] = np.nan
df.loc[rng.choice(n, 160, replace=False), "kWh_Acumulado"] = np.nan

# Huecos sin registro (fin de año)
df = df[~(tramo("2024-12-28 08:15", "2024-12-29 15:15") | tramo("2025-12-27 10:30", "2025-12-30 11:30"))]

# 131 lecturas adicionales desfasadas ±1 s
extra = df.sample(131, random_state=1).copy()
extra["FechaHora"] = extra["FechaHora"] + pd.to_timedelta(rng.choice([-1, 1], 131), unit="s")
df = pd.concat([df, extra]).sort_values("FechaHora")

# Formato como la exportación de SQL Server: datetime2 con 7 decimales y 'NULL' en texto
df["FechaHora"] = df["FechaHora"].dt.strftime("%Y-%m-%d %H:%M:%S.0000000")
df = df.astype(object).where(df.notna(), "NULL")

SALIDA.parent.mkdir(parents=True, exist_ok=True)
SALIDA.unlink(missing_ok=True)
with sqlite3.connect(SALIDA) as con:
    con.execute("""CREATE TABLE Datos_varex_14 (FechaHora TEXT, V_AN REAL, V_BN REAL, V_CN REAL,
        V_LL_Prom REAL, V_LN_Prom REAL, I_A REAL, I_B REAL, I_C REAL, I_Prom REAL,
        kW_Demanda REAL, kW_FaseA REAL, kW_FaseB REAL, kW_FaseC REAL, kWh_Acumulado REAL)""")
    con.executemany(f"INSERT INTO Datos_varex_14 VALUES ({','.join('?' * 15)})",
                    df.itertuples(index=False, name=None))
print(f"Base demo creada: {SALIDA} ({len(df):,} registros)")
