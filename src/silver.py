from datetime import date
from pathlib import Path

import pandas as pd
import sqlite3
import json

from pyspark.sql import SparkSession
from pyspark.sql.functions import explode

spark = SparkSession.builder.appName("silver-mineria").master("local[*]").getOrCreate()

ID_FECHA = date.today().strftime("%Y%m%d")

# Procesamiento Sqlite

con = sqlite3.connect(f"raw_data/mina/{ID_FECHA}/origen_mina.sqlite")
tablas = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", con)
print("tablas:", tablas["name"].tolist())

df_mina = {}

for name in tablas["name"].tolist():
    if name == "lotes":
        pdf = pd.read_sql(f"SELECT rowid AS fila_fuente, * FROM {name} ORDER BY rowid", con)
    else:
        pdf = pd.read_sql(f"SELECT * FROM {name}", con)
    df_mina[name] = pdf
    print(f"{name}: {len(pdf)} filas")

con.close()

regiones = df_mina["regiones"]
plantas = df_mina["plantas"]
rajos = df_mina["rajos"]
equipos = df_mina["equipos"]
turnos = df_mina["turnos"]
causas = df_mina["causas"]
lotes = df_mina["lotes"]
detenciones = df_mina["detenciones"]

nombres_plantas = {
    "P. CERRO NORTE": "CERRO NORTE",
    "PLANTA CERRO NORTE": "CERRO NORTE",
    "P. LOA": "LOA",
    "PLANTA LOA": "LOA",
    "P. SALADO": "SALADO",
    "PLANTA SALADO": "SALADO",
    "P. ILLAPEL": "ILLAPEL",
    "PLANTA ILLAPEL": "ILLAPEL",
}

plantas["nombre_planta_std"] = plantas["nombre"].astype(str).str.upper().str.strip().replace(nombres_plantas)

fechas_texto = lotes["fecha"].astype(str).str.lower()
for es, en in {"ene": "jan", "abr": "apr", "ago": "aug", "dic": "dec"}.items():
    fechas_texto = fechas_texto.str.replace(es, en, regex=False)

lotes["fecha"] = pd.to_datetime(
    fechas_texto, format="mixed", dayfirst=True, errors="coerce"
)

# --- 1. CONVERTIR COLUMNAS NUMÉRICAS EN LOTES ---
con_coma = lotes["toneladas_tratadas"].astype(str).str.contains(",", regex=False)
lotes = lotes[~con_coma].copy()
lotes["toneladas_tratadas"] = (
    lotes["toneladas_tratadas"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .astype(float)
)
for col in ["ley_pct", "recuperacion_pct"]:
    lotes[col] = lotes[col].astype(str).str.replace(",", ".").astype(float)
    # Las columnas numéricas en lotes vienen como string

# Excluir lotes con ley o recuperación fuera de rango
invalidos = (
    ~lotes["ley_pct"].between(0, 100) |
    ~lotes["recuperacion_pct"].between(0, 100)
)

lotes = lotes.loc[~invalidos].copy()
lotes = lotes.sort_values("fila_fuente", kind="stable")
duplicados = lotes.duplicated(subset="lote_id", keep="first")
lotes = lotes.loc[~duplicados].copy()

# Excluir lotes fuera del período de análisis (2025)
fuera_periodo = ~lotes["fecha"].dt.year.eq(2025)

lotes = lotes.loc[~fuera_periodo].copy()

# Agregar mes en formato 'YYYY-MM' en lotes para cruzar con costos
lotes["mes_str"] = lotes["fecha"].dt.to_period("M").astype(str)

print(regiones)

# Guardar regiones en Silver
ruta = Path(f"process_data/regiones/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

regiones.to_parquet(ruta / "regiones.parquet", index=False)

print("Regiones guardadas en Silver")

# Guardar plantas en Silver
ruta = Path(f"process_data/plantas/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

plantas.to_parquet(ruta / "plantas.parquet", index=False)

print("Plantas guardadas en Silver")

# Guardar lotes limpios
ruta = Path(f"process_data/lotes/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

lotes.to_parquet(ruta / "lotes.parquet", index=False)

print("Lotes limpios guardados en:", ruta)
print("Total de lotes:", len(lotes))

print("Tonelaje ambiguo:", con_coma.sum())
print("Porcentajes inválidos:", invalidos.sum())
print("Duplicados:", duplicados.sum())
print("Fuera del período:", fuera_periodo.sum())


# Procesamiento CSV

costos = pd.read_csv(
    f"raw_data/costos/{ID_FECHA}/origen_costos_planta.csv",
    sep=";",
    encoding="iso-8859-1",
    dtype=str
)

costos["mes"] = pd.to_datetime(
    costos["mes"],
    format="%Y-%m",
    errors="coerce"
)

costos = costos[costos["energia_clp"] != "energia_clp"].copy()
costos = costos[costos["planta"].astype(str).str.upper().str.strip() != "TOTAL"].copy()

for col in ["energia_clp", "insumos_clp", "mano_obra_clp"]:
    if col in costos.columns:
        costos[col] = (
            costos[col].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        # Forzar a numérico, transformando errores (como strings de texto) en NaN
        costos[col] = pd.to_numeric(costos[col], errors="coerce")

costos["mes_str"] = pd.to_datetime(costos["mes"], errors="coerce").dt.to_period("M").astype(str)

# Estandarizar nombre de planta en costos para hacer el merge con la tabla plantas

costos["nombre_planta"] = costos["planta"].astype(str).str.upper().str.strip().replace(nombres_plantas)

ruta = Path(f"process_data/costos/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

costos.to_parquet(ruta / "costos.parquet", index=False)

print("Costos limpios guardados en:", ruta)


# Procesamiento JSON

formulas = spark.read.option("multiline", True).json(f"raw_data/origen_leyes/{ID_FECHA}/origen_leyes_laboratorio.json")
formulas.printSchema()   

origen_leyes = (formulas
    .select("faena", explode("registros").alias("r"), "reporta", "unidad_ley")
    .select("faena", "r.fecha_muestreo", "r.laboratorio", "r.ley_lab_prom", "r.lote_id", explode("r.muestras").alias("m"), "reporta", "unidad_ley")
    .select("faena", "fecha_muestreo", "laboratorio", "ley_lab_prom", "lote_id", "m.ley", "m.m", "reporta", "unidad_ley"))

origen_leyes = origen_leyes.toPandas()

origen_leyes["ley_lab_prom"] = pd.to_numeric(origen_leyes["ley_lab_prom"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
origen_leyes["ley"] = pd.to_numeric(origen_leyes["ley"].astype(str).str.replace(",", ".", regex=False), errors="coerce")

print("Total de filas:", len(origen_leyes))
print(origen_leyes.dtypes)
print(origen_leyes.head())

ruta = Path(f"process_data/origen_leyes/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

origen_leyes.to_parquet(ruta / "origen_leyes.parquet", index=False)
print("Laboratorio limpio guardado en:", ruta)


# Procesamiento API

def cargar_datos_api(nombre):
    ruta = Path(f"raw_data/mindicador/{ID_FECHA}/{nombre}.json")
    with open(ruta, "r", encoding="utf-8") as datos:
        raw = json.load(datos)
    
    return pd.DataFrame(raw["serie"])

dolar = pd.concat([cargar_datos_api("dólar 2025"), cargar_datos_api("dólar 2026")], ignore_index=True)
libra_cobre = pd.concat([cargar_datos_api("cobre 2025"), cargar_datos_api("cobre 2026")], ignore_index=True)

dolar["fecha"] = pd.to_datetime(
    dolar["fecha"],
    utc=True,
    errors="coerce"
).dt.tz_localize(None).dt.normalize()
dolar["valor"] = pd.to_numeric(dolar["valor"], errors="coerce")

dolar["mes_str"] = dolar["fecha"].dt.to_period("M").astype(str)

libra_cobre["fecha"] = pd.to_datetime(libra_cobre["fecha"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
libra_cobre["valor"] = pd.to_numeric(libra_cobre["valor"], errors="coerce")

# Guardar dólar
ruta = Path(f"process_data/dolar/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

dolar.to_parquet(ruta / "dolar.parquet", index=False)

# Guardar precio del cobre
ruta = Path(f"process_data/libra_cobre/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

libra_cobre.to_parquet(ruta / "libra_cobre.parquet", index=False)

print("Dólar guardado:", len(dolar), "registros")
print("Cobre guardado:", len(libra_cobre), "registros")

print("Fechas inválidas dólar:", dolar["fecha"].isna().sum())
print("Valores inválidos dólar:", dolar["valor"].isna().sum())
print("Fechas inválidas cobre:", libra_cobre["fecha"].isna().sum())
print("Valores inválidos cobre:", libra_cobre["valor"].isna().sum())


