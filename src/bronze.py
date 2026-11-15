import argparse
import logging
import sqlite3
from datetime import date
from pathlib import Path
import os
import shutil
from pathlib import Path
import json
from datetime import datetime, timezone

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


# Registrar qué fuente se utilizó en cada descarga
estado_fuentes = {}

def descargar_indicador(url, nombre):
    print(f"Descargando {nombre} desde {url}...")

    ruta = Path(f"raw_data/mindicador/{ID_FECHA}")
    ruta.mkdir(parents=True, exist_ok=True)

    destino = ruta / f"{nombre}.json"
    respaldo = Path(f"data_original/respaldo_API/{nombre}.json")

    try:
        resp = session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if "serie" in data:
            destino.write_bytes(resp.content)
            fuente = "API"

        else:
            raise ValueError(
                f"La respuesta de {nombre} no tiene la clave 'serie'."
            )

    except (requests.RequestException, ValueError) as e:
        print(f"AVISO: Falló la API de {nombre}: {e}")
        print("Intentando utilizar respaldo...")

        contenido = respaldo.read_bytes()
        data = json.loads(contenido)

        destino.write_bytes(contenido)
        fuente = "RESPALDO"

        print(f"AVISO: Utilizando respaldo de {nombre}")

    estado_fuentes[nombre] = {
        "fuente": fuente,
        "fecha_ejecucion": datetime.now(timezone.utc).isoformat()
    }

    print(f"Guardado en: {destino} | Fuente: {fuente}")

    return data["serie"]

descargar_indicador("https://mindicador.cl/api/dolar/202", "dólar 2025")
descargar_indicador("https://mindicador.cl/api/dolar/2026", "dólar 2026")
descargar_indicador("https://mindicador.cl/api/libra_cobre/2025", "cobre 2025")
descargar_indicador("https://mindicador.cl/api/libra_cobre/2026", "cobre 2026")

ruta_estado = Path(
    f"raw_data/mindicador/{ID_FECHA}/estado_fuentes.json"
)

ruta_estado.write_text(
    json.dumps(estado_fuentes, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Estado de las fuentes guardado en:", ruta_estado)
