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



import numpy as np

# --- 1. CONVERTIR COLUMNAS NUMÉRICAS EN LOTES ---
con_coma = lotes["toneladas_tratadas"].astype(str).str.contains(",", regex=False)
print(f"Lotes excluidos por coma en toneladas: {con_coma.sum()}")
lotes = lotes[~con_coma].copy()
lotes["toneladas_tratadas"] = (
    lotes["toneladas_tratadas"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .astype(float)
)
for col in ["ley_pct", "recuperacion_pct"]:
    lotes[col] = lotes[col].astype(str).str.replace(",", ".").astype(float)
    # Las columnas numéricas en lotes vienen como string (con comas o puntos)
    #for col in ["toneladas_tratadas", "ley_pct", "recuperacion_pct"]:
    #lotes[col] = lotes[col].astype(str).str.replace(",", ".").astype(float)

# Calcular cobre fino con la ley de Operaciones (Definición Principal)
lotes["cobre_fino_op_ton"] = (
    lotes["toneladas_tratadas"] * 
    (lotes["ley_pct"] / 100) * 
    (lotes["recuperacion_pct"] / 100)
)

# --- 2. INTEGRAR LEYES DE LABORATORIO (Definición Alternativa / Híbrida) ---
# origen_leyes tiene los resultados de laboratorio por lote_id
# Agrupamos por lote_id para obtener un promedio de laboratorio si existen múltiples muestras
if not origen_leyes.empty:
    origen_leyes["ley_lab_prom"] = pd.to_numeric(origen_leyes["ley_lab_prom"].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    lab_grouped = origen_leyes.groupby("lote_id")["ley_lab_prom"].first().reset_index()
    lab_grouped.rename(columns={"ley_lab_prom": "ley_lab"}, inplace=True)
    #origen_leyes["ley"] = origen_leyes["ley"].astype(str).str.replace(",", ".").astype(float)
    #lab_grouped = origen_leyes.groupby("lote_id")["ley"].mean().reset_index()
    #lab_grouped.rename(columns={"ley": "ley_lab"}, inplace=True)
    
    # Cruzamos con lotes
    lotes = lotes.merge(lab_grouped, on="lote_id", how="left")
    
    # Definición Híbrida: Si hay ley de laboratorio, se usa; si es NaN, se mantiene la de Operaciones
    lotes["ley_hibrida"] = lotes["ley_lab"].fillna(lotes["ley_pct"])
else:
    lotes["ley_hibrida"] = lotes["ley_pct"]

# Cobre fino con ley híbrida
lotes["cobre_fino_hib_ton"] = (
    lotes["toneladas_tratadas"] * 
    (lotes["ley_hibrida"] / 100) * 
    (lotes["recuperacion_pct"] / 100)
)

# Convertir toneladas de cobre fino a libras (1 tonelada métrica = 2204.62 libras, o dividir por 0.45359237 / 1000)
lotes["libras_finas_op"] = lotes["cobre_fino_op_ton"] * 1000 / 0.45359237
lotes["libras_finas_hib"] = lotes["cobre_fino_hib_ton"] * 1000 / 0.45359237

# Agregar mes en formato 'YYYY-MM' en lotes para cruzar con costos
lotes["mes_str"] = lotes["fecha"].dt.to_period("M").astype(str)

# Agrupar producción por planta y mes
produccion_mensual = lotes.groupby(["planta_id", "mes_str"]).agg({
    "libras_finas_op": "sum",
    "libras_finas_hib": "sum",
    "lote_id": "count" # Para medir cobertura o conteo de lotes
}).reset_index()


# --- 3. LIMPIAR Y PREPARAR COSTOS ---
# Asegurarnos de que costos sea un DataFrame de pandas limpio
if hasattr(costos, "toPandas"):
    costos = costos.toPandas()

# Eliminar posibles filas de cabecera repetidas por error de lectura
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
costos["costo_total_clp"] = costos["energia_clp"] + costos["insumos_clp"] + costos["mano_obra_clp"]

# Estandarizar nombre de planta en costos para hacer el merge con la tabla plantas

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
costos["nombre_planta"] = costos["planta"].astype(str).str.upper().str.strip().replace(nombres_plantas)
plantas["nombre_planta_std"] = plantas["nombre"].astype(str).str.upper().str.strip().replace(nombres_plantas)

# Cruzar costos con plantas para obtener planta_id
costos_unificado = costos.merge(
    plantas, 
    left_on="nombre_planta", 
    right_on="nombre_planta_std", 
    how="left"
)

# Agrupar costos por planta_id y mes
costos_mensual = costos_unificado.groupby(["planta_id", "mes_str"]).agg({
    "costo_total_clp": "sum"
}).reset_index()


# --- 4. PREPARAR TIPO DE CAMBIO (DÓLAR) ---
dolar["mes_str"] = dolar["fecha"].dt.to_period("M").astype(str)
dolar_mensual = dolar.groupby("mes_str")["valor"].mean().reset_index() # Promedio mensual del dólar
dolar_mensual.rename(columns={"valor": "tipo_cambio"}, inplace=True)


# --- 5. UNIR TODO Y CALCULAR EL COSTO DIRECTO POR LIBRA ---
df_final = produccion_mensual.merge(costos_mensual, on=["planta_id", "mes_str"], how="inner")
df_final = df_final.merge(dolar_mensual, on="mes_str", how="inner")

# Convertir CLP a USD
df_final["costo_total_usd"] = df_final["costo_total_clp"] / df_final["tipo_cambio"]

# Calcular Costo Directo por Libra (Principal y Alternativo)
df_final["costo_libra_op"] = df_final["costo_total_usd"] / df_final["libras_finas_op"]
df_final["costo_libra_hib"] = df_final["costo_total_usd"] / df_final["libras_finas_hib"]

# --- 6. RESULTADOS GLOBALES Y DE SENSIBILIDAD ---
#costo_promedio_op = df_final["costo_libra_op"].mean()
#costo_promedio_hib = df_final["costo_libra_hib"].mean()
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