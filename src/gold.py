import pandas as pd
from datetime import date
from pathlib import Path
from tests_gold import ejecutar_tests_gold

ID_FECHA = date.today().strftime("%Y%m%d") 

regiones = pd.read_parquet(f"process_data/regiones/{ID_FECHA}/regiones.parquet")
plantas = pd.read_parquet(f"process_data/plantas/{ID_FECHA}/plantas.parquet")
lotes = pd.read_parquet(f"process_data/lotes/{ID_FECHA}/lotes.parquet")
costos = pd.read_parquet(f"process_data/costos/{ID_FECHA}/costos.parquet")
origen_leyes = pd.read_parquet(f"process_data/origen_leyes/{ID_FECHA}/origen_leyes.parquet")
dolar = pd.read_parquet(f"process_data/dolar/{ID_FECHA}/dolar.parquet")
libra_cobre = pd.read_parquet(f"process_data/libra_cobre/{ID_FECHA}/libra_cobre.parquet")


# Calcular cobre fino con la ley de Operaciones (Definición Principal)
lotes["cobre_fino_op_ton"] = (
    lotes["toneladas_tratadas"] * 
    (lotes["ley_pct"] / 100) * 
    (lotes["recuperacion_pct"] / 100)
)

# Integrar leyes de laboratorio

if not origen_leyes.empty:
    lab_grouped = origen_leyes.groupby("lote_id")["ley_lab_prom"].first().reset_index()
    lab_grouped.rename(columns={"ley_lab_prom": "ley_lab"}, inplace=True)
    
    # Cruzamos con lotes
    lotes = lotes.merge(lab_grouped, on="lote_id", how="left")
    
    # Definición Híbrida: Si hay ley de laboratorio, se usa; si es NaN, se mantiene la de Operaciones
    lotes["ley_hibrida"] = lotes["ley_lab"].fillna(lotes["ley_pct"])
else:
    lotes["ley_hibrida"] = lotes["ley_pct"]

# Calcular cobre fino con ley híbrida
lotes["cobre_fino_hib_ton"] = (
    lotes["toneladas_tratadas"] * 
    (lotes["ley_hibrida"] / 100) * 
    (lotes["recuperacion_pct"] / 100)
)

# Convertir toneladas de cobre fino a libras (1 tonelada métrica = 2204.62 libras, o dividir por 0.45359237 / 1000)
lotes["libras_finas_op"] = lotes["cobre_fino_op_ton"] * 1000 / 0.45359237
lotes["libras_finas_hib"] = lotes["cobre_fino_hib_ton"] * 1000 / 0.45359237

# Definición promedio simple: cada lote toma el promedio simple de la ley de Operaciones
# de su planta-mes, sin ponderar por tonelaje. Tonelaje y recuperación siguen siendo
# los del lote, así la diferencia con la principal sale sólo de cómo se promedia la ley.
lotes["ley_simple"] = lotes.groupby(["planta_id", "mes_str"])["ley_pct"].transform("mean")
lotes["libras_finas_simple"] = (
    lotes["toneladas_tratadas"] *
    (lotes["ley_simple"] / 100) *
    (lotes["recuperacion_pct"] / 100)
) * 1000 / 0.45359237

# Agrupar producción por planta y mes
produccion_mensual = lotes.groupby(["planta_id", "mes_str"]).agg({
    "toneladas_tratadas": "sum",
    "libras_finas_op": "sum",
    "libras_finas_hib": "sum",
    "libras_finas_simple": "sum",
    "lote_id": "count" # Para medir cobertura o conteo de lotes
}).reset_index()

print("Lotes procesados:", len(lotes))
print("Lotes únicos:", lotes["lote_id"].nunique())
print("Pares planta-mes:", len(produccion_mensual))

print(produccion_mensual.head())


# Calcular costo total de planta
costos["costo_total_clp"] = costos["energia_clp"] + costos["insumos_clp"] + costos["mano_obra_clp"]

# Cruzar costos con plantas para obtener planta_id
costos_unificado = costos.merge(
    plantas, 
    left_on="nombre_planta", 
    right_on="nombre_planta_std", 
    how="left"
)

columnas_costos = ["energia_clp", "insumos_clp", "mano_obra_clp"]
costos_unificado["completo"] = costos_unificado[columnas_costos].notna().all(axis=1)

# Agrupar costos por planta_id y mes
costos_mensual = costos_unificado.groupby(["planta_id", "mes_str"]).agg({
    "energia_clp": "sum",
    "insumos_clp": "sum",
    "mano_obra_clp": "sum",
    "costo_total_clp": "sum",
    "completo": "all"
}).reset_index()

# Excluirlos del cálculo
costos_mensual = costos_mensual[costos_mensual["completo"]].drop(columns="completo")

print("Pares planta-mes con costos completos:", len(costos_mensual))
print(costos_mensual.head())

# Tipo de cambio E2: último dólar observado válido de cada mes
dolar_valido = dolar.dropna(subset=["fecha", "valor"]).copy()
dolar_valido = dolar_valido[dolar_valido["valor"] > 0]

dolar_mensual = (
    dolar_valido
    .sort_values("fecha")
    .drop_duplicates(subset="mes_str", keep="last")
    [["mes_str", "fecha", "valor"]]
    .rename(columns={"valor": "tipo_cambio"})
    .reset_index(drop=True)
)

print("Dólar observado de cierre mensual:")
print(
    dolar_mensual[
        dolar_mensual["mes_str"].isin(["2025-01", "2025-12"])
    ]
)

print(dolar_mensual.head())

# Calcular costo por libra
df_final = produccion_mensual.merge(costos_mensual, on=["planta_id", "mes_str"], how="inner")
df_final = df_final.merge(dolar_mensual, on="mes_str", how="inner")

# Convertir CLP a USD
df_final["costo_total_usd"] = df_final["costo_total_clp"] / df_final["tipo_cambio"]

# Calcular Costo Directo por Libra (Principal y Alternativo)
df_final["costo_libra_op"] = df_final["costo_total_usd"] / df_final["libras_finas_op"]
df_final["costo_libra_hib"] = df_final["costo_total_usd"] / df_final["libras_finas_hib"]

# --- 6. RESULTADOS GLOBALES Y DE SENSIBILIDAD ---
costo_promedio_op = df_final["costo_total_usd"].sum() / df_final["libras_finas_op"].sum()
costo_promedio_hib = df_final["costo_total_usd"].sum() / df_final["libras_finas_hib"].sum()


dif_abs = abs(costo_promedio_op - costo_promedio_hib)
dif_porc = (dif_abs / costo_promedio_op) * 100

print("\n==========================================")
print(" RESULTADOS DE SENSIBILIDAD PARA EL INFORME")
print("==========================================")
print(f"Resultado Principal (Ley Operaciones): {costo_promedio_op:.4f} USD/lb")
print(f"Resultado Alternativo (Híbrido Lab):   {costo_promedio_hib:.4f} USD/lb")
print(f"Diferencia Absoluta:                   {dif_abs:.4f} USD/lb")
print(f"Diferencia Porcentual:                 {dif_porc:.2f}%")
print("==========================================")


# Calcular precio mensual del cobre
libra_cobre["mes_str"] = libra_cobre["fecha"].dt.to_period("M").astype(str)

cobre_mensual = libra_cobre.groupby("mes_str")["valor"].mean().reset_index()
cobre_mensual.rename(columns={"valor": "precio_cobre"}, inplace=True)

# Construir dimensión mes
dim_mes = dolar_mensual.merge(
    cobre_mensual,
    on="mes_str",
    how="inner"
)

# Conservar los meses del análisis
dim_mes = dim_mes[
    dim_mes["mes_str"].between("2025-01", "2025-12")
].copy()

dim_mes = dim_mes.rename(columns={
    "mes_str": "anio_mes",
    "tipo_cambio": "tc_clp_usd",
    "precio_cobre": "precio_cobre_usd_lb"
})

fechas = pd.to_datetime(dim_mes["anio_mes"] + "-01")

dim_mes["mes_key"] = fechas.dt.strftime("%Y%m").astype(int)
dim_mes["trimestre"] = fechas.dt.quarter

meses = {
    1: "Enero", 2: "Febrero", 3: "Marzo",
    4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

dim_mes["mes_nombre"] = fechas.dt.month.map(meses)

dim_mes = dim_mes[[
    "mes_key",
    "anio_mes",
    "trimestre",
    "mes_nombre",
    "tc_clp_usd",
    "precio_cobre_usd_lb"
]]

# Verificar dimensión
print("Meses:", len(dim_mes))
print(dim_mes)


# Construir dimensión planta
dim_planta = plantas.copy()

dim_planta = plantas.merge(
    regiones[["region_id", "region"]],
    on="region_id",
    how="left",
    validate="many_to_one"
)

dim_planta["estado_region"] = dim_planta["region"].apply(
    lambda x: "Informada" if pd.notna(x) else "No informada"
)

dim_planta["region"] = dim_planta["region"].fillna("No informada")

dim_planta = dim_planta.rename(columns={
    "nombre_planta_std": "planta_nombre",
    "planta_id": "planta_key",
    "region": "region_nombre"
})

dim_planta.drop(columns=["region_id", "nombre"], inplace=True)

print(dim_planta)


# Construir tabla de hechos

fact_costo_produccion_mensual = df_final[[
    "planta_id",
    "mes_str",
    "energia_clp",
    "insumos_clp",
    "mano_obra_clp",
    "costo_total_clp",
    "costo_total_usd",
    "toneladas_tratadas",
    "libras_finas_op",
    "libras_finas_hib",
    "libras_finas_simple",
    "lote_id"
]].copy()

fact_costo_produccion_mensual = fact_costo_produccion_mensual.rename(columns={
    "planta_id": "planta_key",
    "costo_total_clp": "costo_directo_clp",
    "costo_total_usd": "costo_directo_usd",
    "toneladas_tratadas": "toneladas_validas",
    "libras_finas_op": "libras_finas_ops",
    "libras_finas_hib": "libras_finas_hibridas",
    "lote_id": "n_lotes"
})

fact_costo_produccion_mensual["mes_key"] = (
    fact_costo_produccion_mensual["mes_str"]
    .str.replace("-", "", regex=False)
    .astype(int)
)

fact_costo_produccion_mensual = fact_costo_produccion_mensual.drop(
    columns="mes_str"
)

fact_costo_produccion_mensual["apto_kpi"] = True



# Validar modelo Gold antes de publicar
ejecutar_tests_gold(
    fact_costo_produccion_mensual,
    dim_planta,
    dim_mes
)

# Guardar las tablas solamente si pasaron los tests
tablas_gold = {
    "dim_mes": dim_mes,
    "dim_planta": dim_planta,
    "fact_costo_produccion_mensual": fact_costo_produccion_mensual
}

for nombre, df in tablas_gold.items():

    ruta = Path(f"gold_data/{nombre}/{ID_FECHA}")
    ruta.mkdir(parents=True, exist_ok=True)

    df.to_parquet(ruta / f"{nombre}.parquet", index=False )

    print(f"{nombre} guardada correctamente.")

print("Publicación Gold completada.")