# Dashboard energético — ALICO

Dashboard en Streamlit construido a partir del notebook `analisis_varex14.ipynb` (v0.6).
Arranca con la **EX14 VAREX II** y está preparado para sumar BO3, FL21 y la Totani, y para
cambiar la fuente de datos de **SQLite a Snowflake** sin tocar la analítica.

## Páginas

| Página | Secciones del notebook |
|---|---|
| Resumen | KPIs, energía mensual por estado, potencia diaria y alertas recientes |
| Consumo y operación | 5.1–5.4, 5.7, 5.8 + serie de 15 min por ventana y fase |
| Energía improductiva | 6.1–6.7 (balance, episodios, arranques, sensibilidad, Excel) |
| Línea base y CUSUM | 7.1–7.4 (modelo, métricas ASHRAE 14, CUSUM, kW en producción) |
| Fases y desbalance | 5.5–5.6 (antes/después del filtro activo, detección del cambio) |
| Anomalías | 8.1–8.4 (z robusto, alertas puntuales y sostenidas, panel, CSV) |
| Calidad de datos | 3.1–3.6 y 4 (faltantes, huecos, coherencia física) |

Los umbrales (180 kW, fechas del filtro, períodos base/reporte, z de alertas y tarifa) se
ajustan desde **Parámetros del análisis** en la barra lateral. El **rango de visualización**
solo filtra las gráficas; los cálculos usan siempre todo el histórico.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
```

## Ejecutar con la base SQLite actual

1. Copiar `EX14_VAREX_II.sqlite` a la carpeta del proyecto (o indicar otra carpeta).
2. Copiar `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml` y ajustar
   `sqlite_dir` si la base está en otra carpeta.
3. `streamlit run app.py`

La base se abre en modo **solo lectura**. Si aparece *database is locked*, cerrar SQLiteStudio.

**Probar sin la base real:** `python scripts/generar_datos_demo.py` crea `demo/EX14_VAREX_II.sqlite`
con datos sintéticos de la misma estructura; luego `SQLITE_DIR=demo streamlit run app.py`
(en PowerShell: `$env:SQLITE_DIR="demo"; streamlit run app.py`).

## Servicio local en Windows

El servicio se inicia en el puerto `8501`, escuchando en la red local. El lanzador actual usa
la base sintética de `demo`; para publicar datos reales, actualice `SQLITE_DIR` en
`scripts/iniciar_dashboard.cmd` para que apunte a la carpeta de la base autorizada.

1. Instalar dependencias con las instrucciones de arriba.
2. Desde PowerShell, ejecutar `.\scripts\instalar_servicio.ps1`. Esto registra una tarea que
   arranca al iniciar sesión y la inicia inmediatamente.
3. Para que otros equipos de la misma subred puedan entrar, ejecute **una vez en PowerShell
   como Administrador**:

   ```powershell
   New-NetFirewallRule -DisplayName "Dashboard Energia Varex (LAN)" `
     -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow `
     -Profile Domain -RemoteAddress LocalSubnet
   ```

4. Compartir `http://<IP-local-del-equipo>:8501` con los usuarios de esa red. Para consultar la
   IP, ejecute `ipconfig` y use la dirección IPv4 de la interfaz conectada a esa subred.

La app y la base permanecen en este equipo; no se configura un host en la nube. Esto es una tarea
programada de Windows (no un servicio del Administrador de control de servicios): el equipo debe
estar encendido y la sesión del usuario debe permanecer iniciada. Para detener o quitar la tarea:
`Stop-ScheduledTask -TaskName "Dashboard Energia Varex"` y
`Unregister-ScheduledTask -TaskName "Dashboard Energia Varex"`.
La regla de ejemplo se limita al perfil de dominio y a la subred local; en un equipo administrado,
solicite autorización a TI si no tiene permisos para crearla.

## Migración a Snowflake

1. `pip install "snowflake-connector-python[pandas]"`
2. En `.streamlit/secrets.toml`: `tipo = "snowflake"` y completar `[connections.snowflake]`.
3. En `config.py`, para cada máquina: `snowflake_tabla` (p. ej. `ENERGIA.ION.DATALOG`) y, si
   todas las máquinas comparten tabla, `snowflake_filtro` (p. ej. `"SOURCEID = 319"`).

Nada más cambia: `datos/fuentes.py` normaliza los nombres de columna (Snowflake los devuelve
en MAYÚSCULAS) y la limpieza acepta tanto el texto `'NULL'`/datetime2 de SQLite como
TIMESTAMP y números nativos. También se puede forzar la fuente con la variable de entorno
`FUENTE_DATOS=sqlite|snowflake`.

Con ~70 000 registros por máquina en dos años, cargar todo y calcular en pandas tarda unos
segundos y queda en caché una hora (`ttl` en `ui/estado.py`). Si el volumen crece mucho, el
siguiente paso sería filtrar por fecha en la consulta o crear vistas agregadas en Snowflake.

## Agregar una máquina

Añadir una entrada en `MAQUINAS` de `config.py` con su base/tabla. Las columnas deben seguir
el esquema del ION (`FechaHora, V_AN … kWh_Acumulado`). Si su régimen de producción es
distinto, ajustar el umbral de producción desde la barra lateral.

## Estructura

```
app.py               navegación, barra lateral y carga cacheada
config.py            máquinas, columnas y parámetros por defecto
datos/fuentes.py     FuenteSQLite / FuenteSnowflake (intercambiables)
analitica/           funciones del notebook, sin dependencia de Streamlit
  limpieza.py  eda.py  desbalance.py  improductiva.py  linea_base.py  anomalias.py
  pipeline.py        ejecutar(raw, parametros) -> Resultados ; exportar_excel()
ui/                  caché, paleta y utilidades de gráficas
vistas/              una página por sección
scripts/generar_datos_demo.py
```

El paquete `analitica` se puede usar fuera del dashboard (en un notebook o en una tarea
diaria de alertas):

```python
from datos import crear_fuente
from analitica import ejecutar
from config import Parametros
r = ejecutar(crear_fuente({"tipo": "sqlite"}).leer_mediciones("EX14"), Parametros())
r.alertas.tail()
```
