import argparse
import logging
import sqlite3
from datetime import date
from pathlib import Path
import os
import shutil
from pathlib import Path

import pandas as pd
import requests
from pyspark.sql import SparkSession
from pyspark.sql.functions import explode

spark = SparkSession.builder.appName("extraccion-mineria").master("local[*]").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
print("Spark", spark.version, "listo")

ID_FECHA = date.today().strftime("%Y%m%d")   
print("id_fecha de hoy:", ID_FECHA)


# Extracción Sqlite

con = sqlite3.connect("data_original/origen_mina.sqlite")
tablas = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", con)
print("tablas:", tablas["name"].tolist())

for name in tablas["name"].tolist():
  pdf = pd.read_sql(f"SELECT * FROM {name}", con)
  df = spark.createDataFrame(pdf)
  df.printSchema()
  print("filas:", df.count())
  df.show(5)

  ruta_text = f"raw_data/{name}/{ID_FECHA}"
  ruta = Path(ruta_text).resolve()                     # 1) definir la ruta
  if ruta.exists():
    shutil.rmtree(ruta)
  df.coalesce(1).write.mode("overwrite").parquet(ruta_text)        # 2) escribir el comando de write
  print("guardado en", ruta)

# Extracción CSV

costos = (spark.read
             .option("header", True)
             .option("sep", ";")
             .option("encoding", "iso-8859-1")
             .csv("data_original/origen_costos_planta.csv"))
print("filas:", costos.count(), "| columnas:", len(costos.columns))
costos.show(5, truncate=False)

ruta = f"raw_data/costos/{ID_FECHA}"                     # 1) definir la ruta
costos.write.mode("overwrite").parquet(ruta)            # 2) escribir el comando de write
print("guardado en", ruta)

# Extracción JSON

formulas = spark.read.option("multiline", True).json("data_original/origen_leyes_laboratorio.json")
formulas.printSchema()   # fijate en el tipo anidado: array de structs, y dentro otro array

origen_leyes = (formulas
    .select("faena", explode("registros").alias("r"), "reporta", "unidad_ley")
    .select("faena", "r.fecha_muestreo", "r.laboratorio", "r.ley_lab_prom", "r.lote_id", explode("r.muestras").alias("m"), "reporta", "unidad_ley")
    .select("faena", "fecha_muestreo", "laboratorio", "ley_lab_prom", "lote_id", "m.ley", "m.m", "reporta", "unidad_ley"))
print("filas (origen leyes):", origen_leyes.count())
origen_leyes.show(truncate=False)

ruta = f"raw_data/origen_leyes/{ID_FECHA}"                     # 1) definir la ruta
origen_leyes.write.mode("overwrite").parquet(ruta)            # 2) escribir el comando de write
print("guardado en", ruta)

# Extracción API (Dólar y Cobre con manejo de headers y reintentos)
import time
from requests.adapters import HTTPAdapter, Retry

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def descargar_indicador(url, nombre):
    print(f"Descargando {nombre} desde {url}...")
    try:
        resp = session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "serie" in data:
            return data["serie"]
        else:
            print(f"Aviso: la respuesta de {nombre} no tiene la clave 'serie'.")
            return []
    except Exception as e:
        print(f"Error al descargar {nombre}: {e}")
        return []

# 1. Dólar 2025 y 2026
serie_dolar = descargar_indicador("https://mindicador.cl/api/dolar/2025", "dólar 2025") + \
              descargar_indicador("https://mindicador.cl/api/dolar/2026", "dólar 2026")

if serie_dolar:
    dolar = spark.createDataFrame(pd.DataFrame(serie_dolar))
    print("Filas dólar:", dolar.count())
    ruta_dolar = f"raw_data/dolar/{ID_FECHA}"
    if Path(ruta_dolar).exists():
        shutil.rmtree(ruta_dolar)
    dolar.coalesce(1).write.mode("overwrite").parquet(ruta_dolar)
    print("Guardado en", ruta_dolar)

# 2. Cobre 2025 y 2026 (por si acaso lo necesitas para cruzar precios)
serie_cobre = descargar_indicador("https://mindicador.cl/api/libra_cobre/2025", "cobre 2025") + \
              descargar_indicador("https://mindicador.cl/api/libra_cobre/2026", "cobre 2026")

if serie_cobre:
    cobre = spark.createDataFrame(pd.DataFrame(serie_cobre))
    print("Filas cobre:", cobre.count())
    ruta_cobre = f"raw_data/libra_cobre/{ID_FECHA}"
    if Path(ruta_cobre).exists():
        shutil.rmtree(ruta_cobre)
    cobre.coalesce(1).write.mode("overwrite").parquet(ruta_cobre)
    print("Guardado en", ruta_cobre)