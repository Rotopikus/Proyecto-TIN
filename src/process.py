import pandas as pd
from datetime import date

ID_FECHA = date.today().strftime("%Y%m%d")   

regiones = pd.read_parquet(f"raw_data/regiones/{ID_FECHA}")
plantas = pd.read_parquet(f"raw_data/plantas/{ID_FECHA}")
rajos = pd.read_parquet(f"raw_data/rajos/{ID_FECHA}")
equipos = pd.read_parquet(f"raw_data/equipos/{ID_FECHA}")
turnos = pd.read_parquet(f"raw_data/turnos/{ID_FECHA}")
causas = pd.read_parquet(f"raw_data/causas/{ID_FECHA}")
lotes = pd.read_parquet(f"raw_data/lotes/{ID_FECHA}")
detenciones = pd.read_parquet(f"raw_data/detenciones/{ID_FECHA}")

costos = pd.read_parquet(f"raw_data/costos/{ID_FECHA}")
origen_leyes = pd.read_parquet(f"raw_data/origen_leyes/{ID_FECHA}")
dolar = pd.read_parquet(f"raw_data/dolar/{ID_FECHA}")


# Diccionario con todos los DataFrames
dataframes = {
    "regiones": regiones,
    "plantas": plantas,
    "rajos": rajos,
    "equipos": equipos,
    "turnos": turnos,
    "causas": causas,
    "lotes": lotes,
    "detenciones": detenciones,
    "costos": costos,
    "origen_leyes": origen_leyes,
    "dolar": dolar
}

lotes["fecha"] = pd.to_datetime(
    lotes["fecha"],
    format="mixed",
    dayfirst=True,
    errors="coerce"
)

costos["mes"] = pd.to_datetime(
    costos["mes"],
    format="%Y-%m",
    errors="coerce"
)

dolar["fecha"] = pd.to_datetime(
    dolar["fecha"],
    utc=True,
    errors="coerce"
).dt.tz_localize(None).dt.normalize()


