import pandas as pd
from datetime import date, datetime
from pathlib import Path
import numpy as np
import os

ID_FECHA = date.today().strftime("%Y%m%d")
RUN_ID = os.environ.get("RUN_ID") or datetime.now().strftime("%Y%m%d_%H%M%S_%f")

# Leer lotes limpios de Silver
lotes = pd.read_parquet(
    f"process_data/lotes/{ID_FECHA}/lotes.parquet"
)
costos = pd.read_parquet(
    f"process_data/costos/{ID_FECHA}/costos.parquet"
)
plantas = pd.read_parquet(
    f"process_data/plantas/{ID_FECHA}/plantas.parquet"
)
origen_leyes = pd.read_parquet(
    f"process_data/origen_leyes/{ID_FECHA}/origen_leyes.parquet"
)
dolar = pd.read_parquet(
    f"process_data/dolar/{ID_FECHA}/dolar.parquet"
)
libra_cobre = pd.read_parquet(
    f"process_data/libra_cobre/{ID_FECHA}/libra_cobre.parquet"
)

def test_lotes_limpios(lotes, pruebas):

    # Prueba 1: unicidad de lote_id
    duplicados = int(lotes["lote_id"].duplicated().sum())
    nulos = int(lotes["lote_id"].isna().sum())

    afectados = duplicados + nulos
    pasa = afectados == 0

    pruebas.append({
        "run_id": RUN_ID,
        "prueba": "sqlite_lotes_unicos",
        "que_verifica": "lote_id único y no nulo en Silver",
        "resultado": "PASA" if pasa else "FALLA",
        "filas_afectadas": afectados,
        "accion_si_falla": "Bloquear Gold",
        "detalle": "Sin incidencias" if pasa else f"{afectados} registros inválidos"
    })

    return pasa

def test_costos(costos, plantas, pruebas):

    # Verificar que todas las plantas de costos existan en SQLite
    no_reconocidos = (
        costos["nombre_planta"].isna() |
        ~costos["nombre_planta"].isin(plantas["nombre_planta_std"])
    )

    afectados = int(no_reconocidos.sum())

    pasa = afectados == 0 and not costos.empty

    pruebas.append({
        "run_id": RUN_ID,
        "prueba": "csv_plantas_reconocidas",
        "que_verifica": "CSV no vacío y todas las plantas reconocidas en SQLite",
        "resultado": "PASA" if pasa else "FALLA",
        "filas_afectadas": afectados,
        "accion_si_falla": "Bloquear Gold",
        "detalle": "Sin incidencias" if pasa else f"{afectados} registros inválidos"
    })

    return pasa

def test_laboratorio(origen_leyes, pruebas):

    # Verificar identificadores y leyes válidas
    invalidos = (
        origen_leyes["lote_id"].isna() |
        origen_leyes["ley_lab_prom"].isna() |
        ~origen_leyes["ley_lab_prom"].between(0, 100)
    )

    afectados = int(invalidos.sum())
    pasa = afectados == 0 and not origen_leyes.empty

    pruebas.append({
        "run_id": RUN_ID,
        "prueba": "json_laboratorio_valido",
        "que_verifica": "JSON no vacío, lote_id presente y ley_lab_prom válida entre 0 y 100",
        "resultado": "PASA" if pasa else "FALLA",
        "filas_afectadas": afectados,
        "accion_si_falla": "Bloquear Gold",
        "detalle": "Sin incidencias" if pasa else f"{afectados} registros inválidos"
    })

    return pasa

def test_api(dolar, libra_cobre, pruebas):

    meses_esperados = {f"2025-{m:02d}" for m in range(1, 13)}

    afectados = 0
    detalles = []

    for nombre, df in [("dolar", dolar), ("cobre", libra_cobre)]:

        # Verificar fechas y valores
        invalidos = (
            df["fecha"].isna() |
            df["valor"].isna() |
            ~np.isfinite(df["valor"]) |
            (df["valor"] <= 0)
        )

        n_invalidos = int(invalidos.sum())
        afectados += n_invalidos

        # Comprobar cobertura mensual de 2025 con datos válidos
        fechas_validas = df.loc[~invalidos, "fecha"]

        meses_presentes = set(
            fechas_validas[fechas_validas.dt.year == 2025]
            .dt.strftime("%Y-%m")
        )

        faltantes = sorted(meses_esperados - meses_presentes)

        if n_invalidos > 0:
            detalles.append(f"{nombre}: {n_invalidos} registros inválidos")

        if faltantes:
            detalles.append(f"{nombre}: faltan {', '.join(faltantes)}")

    pasa = afectados == 0 and len(detalles) == 0

    pruebas.append({
        "run_id": RUN_ID,
        "prueba": "api_datos_validos",
        "que_verifica": "Dólar y cobre: fechas, valores positivos y cobertura de los 12 meses de 2025",
        "resultado": "PASA" if pasa else "FALLA",
        "filas_afectadas": afectados,
        "accion_si_falla": "Bloquear Gold",
        "detalle": "; ".join(detalles) if detalles else "Sin incidencias"
    })

    return pasa

# Lista de resultados de calidad
pruebas = []

# Ejecutar tests
resultados = [
    test_lotes_limpios(lotes, pruebas),
    test_costos(costos, plantas, pruebas),
    test_laboratorio(origen_leyes, pruebas),
    test_api(dolar, libra_cobre, pruebas)
]

# Guardar evidencia
ruta = Path(f"process_data/calidad/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

df_pruebas = pd.DataFrame(pruebas)

df_pruebas.to_csv(
    ruta / f"pruebas_{RUN_ID}.csv",
    index=False
)

print(df_pruebas)

# Revisar si las pruebas pasaron
if not all(resultados):
    raise RuntimeError("Una o más pruebas de calidad fallaron. Revisa el reporte para más detalles")

print("Todas las pruebas de calidad pasaron.")