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

import time
from requests.adapters import HTTPAdapter, Retry

spark = SparkSession.builder.appName("extraccion-mineria").master("local[*]").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
print("Spark", spark.version, "listo")

ID_FECHA = date.today().strftime("%Y%m%d")   
print("id_fecha de hoy:", ID_FECHA)


# Extracción Sqlite

origen = Path("data_original/origen_mina.sqlite")
ruta = Path(f"raw_data/mina/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)
destino = ruta / origen.name
shutil.copy2(origen, destino)
print("Sqlite original guardado en:", destino)


# Extracción CSV

origen = Path("data_original/origen_costos_planta.csv")
ruta = Path(f"raw_data/costos/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)
destino = ruta / origen.name
shutil.copy2(origen, destino)
print("CSV original guardado en:", destino)


# Extracción JSON

origen = Path("data_original/origen_leyes_laboratorio.json")
ruta = Path(f"raw_data/origen_leyes/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)
destino = ruta / origen.name
shutil.copy2(origen, destino)
print("JSON original guardado en:", destino)


# Extracción API (Dólar y Cobre con manejo de headers y reintentos)

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
            ruta = Path(f"raw_data/mindicador/{ID_FECHA}")
            ruta.mkdir(parents=True, exist_ok=True)

            destino = ruta / f"{nombre}.json"
            destino.write_bytes(resp.content)

            print("Guardado en:", destino)
            return data["serie"]
        else:
            print(f"Aviso: la respuesta de {nombre} no tiene la clave 'serie'.")
            return []
    except Exception as e:
        print(f"Error al descargar {nombre}: {e}")
        return []

descargar_indicador("https://mindicador.cl/api/dolar/2025", "dólar 2025")
descargar_indicador("https://mindicador.cl/api/dolar/2026", "dólar 2026")
descargar_indicador("https://mindicador.cl/api/libra_cobre/2025", "cobre 2025")
descargar_indicador("https://mindicador.cl/api/libra_cobre/2026", "cobre 2026")
