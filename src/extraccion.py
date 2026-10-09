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

# Extyracción API

resp = requests.get("https://mindicador.cl/api/dolar/2025", timeout=20)
resp2 = requests.get("https://mindicador.cl/api/dolar/2026", timeout=20)
print("codigo de respuesta:", resp.status_code)   # 200 = OK
serie = resp.json()["serie"] + resp2.json()["serie"]

dolar = spark.createDataFrame(pd.DataFrame(serie))
print("filas:", dolar.count())
dolar.show(5)

ruta = f"raw_data/dolar/{ID_FECHA}"                     # 1) definir la ruta
dolar.coalesce(1).write.mode("overwrite").parquet(ruta)            # 2) escribir el comando de write
print("guardado en", ruta)



for tabla in sorted(os.listdir("raw_data")):
    print("raw_data/%s -> %s" % (tabla, os.listdir(f"raw_data/{tabla}")))

print()
dolar_raw = spark.read.parquet(f"raw_data/dolar/{ID_FECHA}")
print("releido de raw_data/dolar:", dolar_raw.count(), "filas")
dolar_raw.show(3)

spark.stop()
