import pandas as pd
import numpy as np
from datetime import date, datetime
from pathlib import Path

ID_FECHA = date.today().strftime("%Y%m%d")
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

fact = pd.read_parquet(
    f"gold_data/fact_costo_produccion_mensual/{ID_FECHA}/fact_costo_produccion_mensual.parquet"
)

dim_planta = pd.read_parquet(
    f"gold_data/dim_planta/{ID_FECHA}/dim_planta.parquet"
)

dim_mes = pd.read_parquet(
    f"gold_data/dim_mes/{ID_FECHA}/dim_mes.parquet"
)

def registrar(pruebas, nombre, descripcion, afectados, detalle):
    pasa = afectados == 0

    pruebas.append({
        "run_id": RUN_ID,
        "prueba": nombre,
        "que_verifica": descripcion,
        "resultado": "PASA" if pasa else "FALLA",
        "filas_afectadas": afectados,
        "accion_si_falla": "Bloquear Gold",
        "detalle": detalle
    })

    return pasa

def test_clave_hechos(fact, pruebas):

    duplicados = int(
        fact.duplicated(subset=["planta_key", "mes_key"]).sum()
    )

    nulos = int(
        fact[["planta_key", "mes_key"]].isna().any(axis=1).sum()
    )

    afectados = duplicados + nulos

    return registrar(
        pruebas,
        "gold_clave_hechos",
        "Cada combinación planta_key y mes_key es única y no nula",
        afectados,
        "Sin incidencias" if afectados == 0 else f"{afectados} problemas de clave"
    )

def test_integridad_referencial(fact, dim_planta, dim_mes, pruebas):

    plantas_huerfanas = int(
        (~fact["planta_key"].isin(dim_planta["planta_key"])).sum()
    )

    meses_huerfanos = int(
        (~fact["mes_key"].isin(dim_mes["mes_key"])).sum()
    )

    claves_plantas_invalidas = int(
        dim_planta["planta_key"].isna().sum() +
        dim_planta["planta_key"].duplicated().sum()
    )

    claves_meses_invalidas = int(
        dim_mes["mes_key"].isna().sum() +
        dim_mes["mes_key"].duplicated().sum()
    )

    afectados = (
        plantas_huerfanas + meses_huerfanos +
        claves_plantas_invalidas + claves_meses_invalidas
    )

    return registrar(
        pruebas,
        "gold_integridad_referencial",
        "Claves de dimensiones únicas y sin huérfanos en el hecho",
        afectados,
        "Sin incidencias" if afectados == 0 else f"{afectados} problemas de integridad"
    )

def test_rangos_hechos(fact, pruebas):

    columnas = [
        "energia_clp",
        "insumos_clp",
        "mano_obra_clp",
        "costo_directo_clp",
        "costo_directo_usd",
        "toneladas_validas",
        "libras_finas_ops",
        "libras_finas_hibridas",
        "n_lotes"
    ]

    valores = fact[columnas].apply(pd.to_numeric, errors="coerce")

    no_finitos = ~pd.Series(
        np.isfinite(valores.to_numpy(dtype=float)).all(axis=1),
        index=fact.index
    )

    positivos = [
        "costo_directo_clp",
        "costo_directo_usd",
        "toneladas_validas",
        "libras_finas_ops",
        "libras_finas_hibridas",
        "n_lotes"
    ]

    no_positivos = (valores[positivos] <= 0).any(axis=1)

    componentes = ["energia_clp", "insumos_clp", "mano_obra_clp"]
    negativos = (valores[componentes] < 0).any(axis=1)

    afectados = int((no_finitos | no_positivos | negativos).sum())

    return registrar(
        pruebas,
        "gold_rangos_validos",
        "Costos válidos, producción positiva y medidas no nulas ni infinitas",
        afectados,
        "Sin incidencias" if afectados == 0 else f"{afectados} filas con valores inválidos"
    )

def test_periodo_hechos(fact, dim_mes, pruebas):

    meses_validos = set(range(202501, 202513))

    fuera_hecho = int(
        (~fact["mes_key"].isin(meses_validos)).sum()
    )

    fuera_dimension = int(
        (~dim_mes["mes_key"].isin(meses_validos)).sum()
    )

    afectados = fuera_hecho + fuera_dimension

    return registrar(
        pruebas,
        "gold_periodo_2025",
        "Hechos y dimensión mes pertenecen al período enero-diciembre 2025",
        afectados,
        "Sin incidencias" if afectados == 0 else f"{afectados} registros fuera del período"
    )

pruebas = []

resultados = [
    test_clave_hechos(fact, pruebas),
    test_integridad_referencial(fact, dim_planta, dim_mes, pruebas),
    test_rangos_hechos(fact, pruebas),
    test_periodo_hechos(fact, dim_mes, pruebas)
]

ruta = Path(f"gold_data/calidad/{ID_FECHA}")
ruta.mkdir(parents=True, exist_ok=True)

df_pruebas = pd.DataFrame(pruebas)

df_pruebas.to_csv(
    ruta / f"pruebas_{RUN_ID}.csv",
    index=False
)

print(df_pruebas.to_string(index=False))

if not all(resultados):
    raise RuntimeError(
        "Una o más pruebas Gold fallaron. Revisa el reporte."
    )

print("Todas las pruebas Gold pasaron.")