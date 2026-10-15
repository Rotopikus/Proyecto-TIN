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
n_lotes_originales = len(lotes)
detenciones = pd.read_parquet(f"raw_data/detenciones/{ID_FECHA}")

costos = pd.read_parquet(f"raw_data/costos/{ID_FECHA}")
origen_leyes = pd.read_parquet(f"raw_data/origen_leyes/{ID_FECHA}")
dolar = pd.read_parquet(f"raw_data/dolar/{ID_FECHA}")
libra_cobre = pd.read_parquet(f"raw_data/libra_cobre/{ID_FECHA}")

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

fechas_texto = lotes["fecha"].astype(str).str.lower()
for es, en in {"ene": "jan", "abr": "apr", "ago": "aug", "dic": "dec"}.items():
    fechas_texto = fechas_texto.str.replace(es, en, regex=False)

lotes["fecha"] = pd.to_datetime(
    fechas_texto, format="mixed", dayfirst=True, errors="coerce"
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

columnas_costos = ["energia_clp", "insumos_clp", "mano_obra_clp"]
costos_unificado["completo"] = costos_unificado[columnas_costos].notna().all(axis=1)

# Agrupar costos por planta_id y mes
costos_mensual = costos_unificado.groupby(["planta_id", "mes_str"]).agg({
    "costo_total_clp": "sum",
    "completo": "all"
}).reset_index()

# Excluirlos del cálculo
costos_mensual = costos_mensual[costos_mensual["completo"]].drop(columns="completo")


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

# --- 7. EVIDENCIA Y GRÁFICOS (ÍTEM E) ---
# Se reutiliza df_final: no se releen ni exportan tablas intermedias.
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Guarda PNG sin abrir ventanas
import matplotlib.pyplot as plt

def generar_graficos(df_final, plantas, libra_cobre, n_lotes_originales):
    graficos = Path(__file__).resolve().parent.parent / "graficos"
    graficos.mkdir(exist_ok=True)

    # Consolidar por mes: dividir sumas, NO promediar costos por planta.
    mensual = df_final.groupby("mes_str").agg(
        costo_clp=("costo_total_clp", "sum"),
        costo_usd=("costo_total_usd", "sum"),
        libras=("libras_finas_op", "sum"),
        tc=("tipo_cambio", "first"),
        plantas=("planta_id", "nunique"),
    )
    mensual["costo"] = mensual.costo_usd / mensual.libras
    mensual["costo_clp_lb"] = mensual.costo_clp / mensual.libras
    mensual["tc_fijo"] = mensual.costo_clp_lb / mensual.loc["2025-01", "tc"]

    # Única fuente adicional: cobre ya extraído en extraccion.py.
    cobre = libra_cobre.copy()
    cobre["fecha"] = pd.to_datetime(cobre.fecha, utc=True, errors="coerce").dt.tz_localize(None)
    cobre["valor"] = pd.to_numeric(cobre.valor, errors="coerce")
    precio = cobre.groupby(cobre.fecha.dt.strftime("%Y-%m"))["valor"].mean()
    mensual["precio"] = precio.reindex(mensual.index)
    if mensual["precio"].isna().any():
        raise ValueError("Falta precio del cobre para uno o más meses del análisis.")
    mensual["brecha"] = mensual.precio - mensual.costo

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 200})

    def guardar(fig, archivo, nota):
        fig.text(0.02, 0.025, nota, fontsize=8, color="dimgray")
        fig.savefig(graficos / archivo, bbox_inches="tight")
        plt.close(fig)

    # FIGURA 1: evolución mensual del costo, precio y tipo de cambio fijo.
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(mensual))
    ax.plot(x, mensual.precio, "s-", label="Precio del cobre")
    ax.plot(x, mensual.costo, "o-", label="Costo de planta")
    ax.plot(x, mensual.tc_fijo, "--", label="Costo con dólar de enero")
    # Nombres de los meses
    meses = ["ene", "feb", "mar", "abr", "may", "jun",
            "jul", "ago", "sep", "oct", "nov", "dic"]

    ax.set_xticks(x, [meses[int(m[-2:]) - 1] for m in mensual.index])

    # Eje Y desde cero, con intervalos uniformes de 2 USD/lb
    max_y = mensual[["precio", "costo", "tc_fijo"]].max().max()
    limite_y = 2 * np.ceil((max_y + 0.2) / 2)

    print("\n==========================================")
    print(" RESULTADOS DE CAMBIO DE PRECIO Y COSTO")
    print("==========================================")
    print(f"Precio en Enero: {mensual.loc["2025-01", "precio"]:.3f} USD/lb")
    print(f"Precio en Diciembre: {mensual.loc["2025-12", "precio"]:.3f} USD/lb")
    print(f"Costo en Enero: {mensual.loc["2025-01", "costo"]:.3f} USD/lb")
    print(f"Costo en Diciembre:  {mensual.loc["2025-12", "costo"]:.3f} USD/lb")
    print("==========================================")

    ax.set_ylim(0, limite_y)
    ax.set_yticks(np.arange(0, limite_y + 1, 2))

    ax.set(xlabel="Mes de 2025", ylabel="USD/lb",
        title="Figura 1. Evolución mensual del costo y precio del cobre (USD/lb)")

    ax.grid(axis="y", alpha=0.25)

    # Leyenda debajo del gráfico
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
            ncol=3, frameon=False)

    fig.subplots_adjust(bottom=0.30)
    guardar(fig, "figura_1.png", "Fuente: SQLite, CSV minería 3 y mindicador.cl.")

    # FIGURA 2: descomposición exacta del cambio de brecha enero-diciembre.
    enero, dic = mensual.loc["2025-01"], mensual.loc["2025-12"]
    cambios = [dic.precio - enero.precio,
               -(dic.costo_clp_lb - enero.costo_clp_lb) / enero.tc,
               -dic.costo_clp_lb * (1 / dic.tc - 1 / enero.tc)]
    niveles = [enero.brecha]
    for cambio in cambios:
        niveles.append(niveles[-1] + cambio)
    if not np.isclose(niveles[-1], dic.brecha):
        raise AssertionError("La descomposición precio/costos/dólar no cierra.")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(0, niveles[0], color="steelblue")
    for i, (antes, despues) in enumerate(zip(niveles[:-1], niveles[1:]), 1):
        ax.bar(i, abs(despues - antes), bottom=min(antes, despues),
               color="seagreen" if despues >= antes else "indianred")
    ax.bar(4, niveles[-1], color="steelblue")
    for i, valor in enumerate([niveles[0], *cambios, niveles[-1]]):
        base = (0 if i in (0, 4) else min(niveles[i-1], niveles[i]))
        altura = abs(valor) if i not in (0, 4) else max(valor, 0)
        ax.text(i, base + altura + 0.06, f"{valor:+.2f}" if i in (1, 2, 3)
                else f"{valor:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(5), ["Enero", "Precio", "Costo en CLP", "Dólar", "Diciembre"])
    ax.set(ylabel="USD/lb", title="Figura 2. Cambio de la brecha (USD/lb)")
    ax.axhline(0, color="gray", linewidth=0.6)
    ax.grid(axis="y", alpha=0.25)
    fig.subplots_adjust(bottom=0.18)
    guardar(fig, "figura_2.png", "Precio del cobre menos costo de planta. Fuente: CSV Minería y mindicador.cl. Brecha no equivale a utilidad.")

    # FIGURA 3: comparación de costos por planta, misma métrica ya calculada.
    por_planta = df_final.merge(plantas[["planta_id", "nombre"]], on="planta_id", how="left")
    comparacion = por_planta.pivot(index="nombre", columns="mes_str", values="costo_libra_op")
    comparacion = comparacion.reindex(columns=["2025-01", "2025-12"]).dropna(how="all")
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(comparacion))
    ax.barh(y - 0.18, comparacion["2025-01"], 0.35, label="Enero")
    ax.barh(y + 0.18, comparacion["2025-12"], 0.35, label="Diciembre")
    ax.set_yticks(y, [str(nombre).replace("Planta ", "") for nombre in comparacion.index])
    ax.invert_yaxis()
    max_costo = comparacion[["2025-01", "2025-12"]].max().max()
    ax.set_xlim(0, max_costo * 1.18)
    for j, mes in enumerate(["2025-01", "2025-12"]):
        for i, valor in enumerate(comparacion[mes]):
            if pd.notna(valor):
                ax.text(valor + max_costo * 0.015, i + (j - 0.5) * 0.36,
                        f"{valor:.2f}", va="center", fontsize=8)
    ax.set(xlabel="USD/lb", title="Figura 3. Costo por planta: enero vs. diciembre (USD/lb)")
    ax.legend()
    ax.grid(axis="x", alpha=0.25)
    fig.subplots_adjust(left=0.22, bottom=0.18)
    guardar(fig, "figura_3.png", "Fuente: SQLite, CSV Minería 3 y mindicador.cl. Ley de Operaciones y datos válidos.")

    # Cobertura e impacto ilustrativo: se calculan a partir del mismo df_final.
    n_costo_cero = int(df_final.costo_total_clp.eq(0).sum())
    if n_costo_cero:
        print(f"ADVERTENCIA: {n_costo_cero} pares planta-mes tienen costo cero. Revisar costos faltantes.")
    incluidos = int(df_final.lote_id.sum())
    excluidos = n_lotes_originales - incluidos

    # --- CASO DE NEGOCIO: ENERO VS DICIEMBRE ---

    ene = df_final[df_final["mes_str"] == "2025-01"].set_index("planta_id")
    dic = df_final[df_final["mes_str"] == "2025-12"].set_index("planta_id")

    # Verificar que se comparen las mismas plantas
    if set(ene.index) != set(dic.index):
        raise ValueError("Faltan plantas en enero o diciembre.")

    # Costo unitario en pesos de enero por planta
    costo_enero_clp_lb = ene["costo_total_clp"] / ene["libras_finas_op"]

    # Costo hipotético de diciembre usando el costo unitario de enero
    costo_hipotetico = (costo_enero_clp_lb * dic["libras_finas_op"]).sum()

    # Costo real de diciembre
    costo_real = dic["costo_total_clp"].sum()

    # Diferencia y escenario ilustrativo
    brecha = costo_real - costo_hipotetico
    escenario_10 = brecha * 0.10

    print("\n========== CASO DE NEGOCIO ==========")
    print(f"Costo real diciembre: ${costo_real:,.0f} CLP")
    print(f"Costo hipotético:     ${costo_hipotetico:,.0f} CLP")
    print(f"Brecha:              ${brecha:,.0f} CLP")
    print(f"Escenario 10%:       ${escenario_10:,.0f} CLP")
    print("=====================================")

generar_graficos(df_final, plantas, libra_cobre, n_lotes_originales)

# --- 8. COBERTURA DE DATOS ---
incluidos = int(df_final["lote_id"].sum())
excluidos = n_lotes_originales - incluidos
sin_costos = len(lotes) - incluidos

pares = len(df_final)
pares_posibles = plantas["planta_id"].nunique() * 12

print("\n========== COBERTURA DE DATOS ==========")
print(f"Lotes originales: {n_lotes_originales}")
print(f"Lotes incluidos: {incluidos}")
print(f"Lotes excluidos: {excluidos} ({excluidos/n_lotes_originales:.2%})")
print(f"Tonelaje ambiguo: {con_coma.sum()}")
print(f"Ley o recuperación inválida: {invalidos.sum()}")
print(f"Duplicados: {duplicados.sum()}")
print(f"Fuera de 2025: {fuera_periodo.sum()}")
print(f"Sin costos completos o disponibles: {sin_costos}")
print(f"Pares planta-mes: {pares} de {pares_posibles} ({pares/pares_posibles:.2%})")
print("=========================================")