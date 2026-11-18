"""Prototipo de la E2: una pantalla que responde la pregunta del grupo con la capa oro.

Lee la última corrida de la cadena (gold_data/) y toma la métrica de src/metrica.py,
así que el número es el mismo que imprime run.sh para el informe. Cuando la cadena
vuelve a correr, la pantalla se recarga sola.
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import metrica as m  # noqa: E402

PREGUNTA = (
    "¿El costo directo de planta por libra de cobre fino subió o bajó en 2025, "
    "y cómo se compara con lo que hizo el precio del cobre?"
)
AUDIENCIA = (
    "Para la Gerencia de Operaciones de CuprumAndes, en la revisión mensual de costos. "
    "Sirve para decidir en qué planta actuar primero y si el resultado del año viene del precio o del desempeño."
)

# Paleta validada con el validador de dataviz (modo claro, superficie #fcfcfb).
AZUL = "#2a78d6"
AZUL_CLARO = "#86b6ef"
NARANJO = "#eb6834"
AQUA = "#1baf7a"
VIOLETA = "#6250d6"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
GRILLA = "#e1e0d9"
SUPERFICIE = "#fcfcfb"

SERIE_COSTO = "Costo directo por libra"
SERIE_COBRE = "Precio del cobre"

st.set_page_config(
    page_title="Costo directo por libra · CuprumAndes",
    page_icon=":material/factory:",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 90rem; }
    h1 { font-size: 2.1rem !important; line-height: 1.25 !important; }
    .hero { padding: 1.25rem 1.5rem; border: 1px solid rgba(11,11,11,0.10); border-radius: 0.75rem;
            background: #ffffff; height: 100%; }
    .hero-etiqueta { color: #52514e; font-size: 0.95rem; line-height: 1.4; }
    .hero-valor { font-size: 3.4rem; font-weight: 700; line-height: 1.1; margin: 0.35rem 0 0.5rem; color: #0b0b0b; }
    .hero-valor span { font-size: 1.4rem; font-weight: 500; color: #52514e; }
    .hero-respuesta { font-size: 1.05rem; line-height: 1.5; color: #0b0b0b; }
    .hero-nota { font-size: 0.85rem; line-height: 1.45; color: #52514e; margin-top: 0.6rem; }
    .pie { font-size: 0.85rem; line-height: 1.6; color: #52514e; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Leyendo la última corrida de la cadena…")
def cargar(firma: tuple[str, float]) -> m.Corrida:
    # La firma es la llave del caché: cambia cuando la cadena reescribe la capa oro.
    return m.cargar_corrida(id_fecha=firma[0])


@st.fragment(run_every="10s")
def vigilar_cadena(firma_vista: tuple[str, float] | None) -> None:
    try:
        firma_actual = m.firma()
    except FileNotFoundError:
        return
    if firma_actual != firma_vista:
        st.rerun()


def nombre_planta(nombre: str) -> str:
    return nombre.title()


def eje_decimal(decimales: int) -> str:
    return f"replace(format(datum.value, '.{decimales}f'), '.', ',')"


def variacion(inicial: float, final: float) -> float:
    return final / inicial - 1


def extremos(mensual: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Primer y último mes del período que tienen costo, que son los que se comparan."""
    con_dato = mensual.dropna(subset=["costo_por_libra"])
    return con_dato.iloc[0], con_dato.iloc[-1]


def porcentaje(valor: float, decimales: int = 1) -> str:
    return "sin dato" if pd.isna(valor) else f"{m.formato(100 * valor, decimales, signo=True)} %"


def enumerar(elementos: list[str]) -> str:
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


# ---------------------------------------------------------------- datos
try:
    firma = m.firma()
except FileNotFoundError as error:
    st.title(PREGUNTA)
    st.error(str(error))
    vigilar_cadena(None)
    st.stop()

corrida = cargar(firma)
vigilar_cadena(firma)

meses = corrida.dim_mes["anio_mes"].tolist()
plantas_todas = corrida.dim_planta["planta_nombre"].tolist()

# ---------------------------------------------------------------- título y filtros
st.title(PREGUNTA)
st.caption(AUDIENCIA)

f1, f2, f3 = st.columns([1, 1.25, 1.75], gap="large")
with f1:
    mes_inicial, mes_final = st.select_slider(
        "Período", options=meses, value=(meses[0], meses[-1]), format_func=m.nombre_mes, key="periodo",
        bind="query-params",
    )
with f2:
    plantas = st.multiselect(
        "Plantas", options=plantas_todas, default=plantas_todas, format_func=nombre_planta, key="plantas",
        bind="query-params",
    )
with f3:
    ley = st.radio(
        "**Ley con que se calcula el cobre fino** · hay tres; al cambiarla cambia toda la pantalla",
        options=corrida.definiciones,
        format_func=lambda clave: m.DEFINICIONES[clave].etiqueta,
        horizontal=True,
        key="ley",
        bind="query-params",
    )
    st.caption(m.DEFINICIONES[ley].regla)

faltantes = [d.etiqueta for c, d in m.DEFINICIONES.items() if c not in corrida.definiciones]
if faltantes:
    st.warning(
        f"La corrida {corrida.id_fecha} no trae las libras finas de {', '.join(faltantes)}. "
        "Esas leyes vuelven a aparecer en el selector cuando la cadena las publique en la tabla de hechos.",
        icon=":material/warning:",
    )

if not plantas:
    st.info("Elige al menos una planta para ver la cifra.", icon=":material/info:")
    st.stop()

df = corrida.planta_mes[
    corrida.planta_mes["anio_mes"].between(mes_inicial, mes_final)
    & corrida.planta_mes["planta_nombre"].isin(plantas)
]
etiqueta_periodo = (
    m.nombre_mes(mes_inicial) if mes_inicial == mes_final
    else f"{m.nombre_mes(mes_inicial)} a {m.nombre_mes(mes_final)}"
)
if df.empty:
    st.info("No hay plantas con costos completos en el período elegido. Amplía el período o agrega plantas.",
            icon=":material/info:")
    st.stop()
mensual = m.por_mes(df, corrida.dim_mes, ley, mes_inicial, mes_final)
inicio, fin = extremos(mensual)
cifra = m.costo_por_libra(df, ley)
cob = m.cobertura(corrida, df, mes_inicial, mes_final, len(plantas))

# Cada filtro y la pestaña quedan en la URL, así un estado de la pantalla se comparte con un enlace.
tab_respuesta, tab_leyes = st.tabs(["Respuesta", "Comparar las tres leyes"], key="vista", bind="query-params")

# ---------------------------------------------------------------- pestaña 1
with tab_respuesta:
    h1, h2, h3, h4 = st.columns([1.6, 1, 1, 1], gap="medium")

    var_costo = variacion(inicio["costo_por_libra"], fin["costo_por_libra"])
    var_cobre = variacion(inicio["precio_cobre"], fin["precio_cobre"])
    verbo = "Subió" if var_costo > 0 else "Bajó" if var_costo < 0 else "Se mantuvo"
    compara = inicio["anio_mes"] != fin["anio_mes"]
    if not compara:
        respuesta = "Elige un período con al menos dos meses con costos para ver si el costo subió o bajó."
    else:
        respuesta = (
            f"<b>{verbo}.</b> Pasó de {m.formato(inicio['costo_por_libra'])} USD/lb en {inicio['mes']} "
            f"a {m.formato(fin['costo_por_libra'])} en {fin['mes']} ({m.formato(100 * var_costo, 1, signo=True)} %), "
            f"mientras el precio del cobre varió {m.formato(100 * var_cobre, 1, signo=True)} %."
        )
    otras = " · ".join(
        f"{m.DEFINICIONES[c].etiqueta}: {m.formato(m.costo_por_libra(df, c))}"
        for c in corrida.definiciones if c != ley
    )
    lotes_txt = f"{m.formato(cob['lotes'], 0)} lotes válidos"
    if cob["lotes_originales"]:
        excluidos = 100 * (1 - cob["lotes"] / cob["lotes_originales"])
        lotes_txt = (f"{m.formato(cob['lotes'], 0)} de {m.formato(cob['lotes_originales'], 0)} lotes "
                     f"({m.formato(excluidos, 1)} % excluidos por calidad o por falta de costos)")
    with h1:
        st.markdown(
            f"""
            <div class="hero">
              <div class="hero-etiqueta">{m.NOMBRE}, {etiqueta_periodo}, con {m.DEFINICIONES[ley].etiqueta}</div>
              <div class="hero-valor">{m.formato(cifra)} <span>{m.UNIDAD}</span></div>
              <div class="hero-respuesta">{respuesta}</div>
              <div class="hero-nota">Cobertura: {cob['pares']} de {cob['pares_posibles']} pares planta-mes y {lotes_txt}.<br>
              Con las otras leyes, la cifra del período es {otras} USD/lb.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h2:
        st.metric(
            f"Costo por libra en {fin['mes']}",
            f"{m.formato(fin['costo_por_libra'])} USD/lb",
            delta=f"{porcentaje(var_costo)} frente a {inicio['mes']}" if compara else None,
            delta_color="inverse",
            border=True,
            help="Costo directo en USD dividido por las libras finas de las plantas elegidas en ese mes.",
        )
    with h3:
        st.metric(
            f"Precio del cobre en {fin['mes']}",
            f"{m.formato(fin['precio_cobre'])} USD/lb",
            delta=f"{porcentaje(var_cobre)} frente a {inicio['mes']}" if compara else None,
            border=True,
            help="Promedio mensual de la libra de cobre publicada por mindicador.cl.",
        )
    with h4:
        st.metric(
            f"Precio menos costo en {fin['mes']}",
            f"{m.formato(fin['brecha'])} USD/lb",
            delta=f"{porcentaje(variacion(inicio['brecha'], fin['brecha']))} frente a {inicio['mes']}" if compara else None,
            border=True,
            help="Precio del cobre menos costo directo de planta. No es el margen, ya que faltan los costos de mina, "
                 "transporte y depreciación.",
        )

    if inicio["anio_mes"] != mes_inicial or fin["anio_mes"] != mes_final:
        st.caption(
            f"La comparación usa {inicio['mes']} y {fin['mes']}, que son el primer y el último mes del período "
            "con costos completos para las plantas elegidas."
        )

    # Gráfico que explica la cifra
    st.subheader("Costo por libra y precio del cobre, mes a mes")
    largo = pd.concat([
        mensual.assign(serie=SERIE_COSTO, valor=mensual["costo_por_libra"]),
        mensual.assign(serie=SERIE_COBRE, valor=mensual["precio_cobre"]),
    ])
    largo["valor_txt"] = largo["valor"].map(lambda v: "sin dato" if pd.isna(v) else f"{m.formato(v)} USD/lb")
    largo["plantas_txt"] = largo["plantas"].map(lambda n: f"{n} de {len(plantas)}")
    orden_meses = mensual["mes"].tolist()
    color = alt.Color(
        "serie:N",
        scale=alt.Scale(domain=[SERIE_COSTO, SERIE_COBRE], range=[AZUL, NARANJO]),
        legend=alt.Legend(title=None, orient="top", direction="horizontal"),
    )
    x = alt.X("mes:N", sort=orden_meses, title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y("valor:Q", title="USD por libra", scale=alt.Scale(zero=True),
              axis=alt.Axis(labelExpr=eje_decimal(1), gridColor=GRILLA, tickCount=6))
    tooltip = [
        alt.Tooltip("mes:N", title="Mes"),
        alt.Tooltip("serie:N", title="Serie"),
        alt.Tooltip("valor_txt:N", title="Valor"),
        alt.Tooltip("plantas_txt:N", title="Plantas con costo"),
    ]
    hover = alt.selection_point(fields=["mes"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(largo).encode(x=x)
    lineas = base.mark_line(strokeWidth=2).encode(y=y, color=color)
    puntos = base.mark_point(filled=True, size=70, stroke=SUPERFICIE, strokeWidth=2, opacity=1).encode(
        y=y, color=color, tooltip=tooltip
    )
    regla = base.mark_rule(color=TINTA_SECUNDARIA, strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(0.35), alt.value(0))
    ).add_params(hover)
    etiquetas = base.transform_filter(alt.datum.mes == fin["mes"]).mark_text(
        align="left", dx=10, fontSize=13, fontWeight="bold"
    ).encode(y=y, text="valor_txt:N", color=alt.value(TINTA))
    grafico = (regla + lineas + puntos + etiquetas).properties(height=340, padding={"right": 90})
    st.altair_chart(grafico, width="stretch")
    parciales = mensual[mensual["plantas"] < len(plantas)]
    nota = "El costo de cada mes es el costo directo en USD dividido por las libras finas de las plantas con costos completos."
    if len(parciales):
        nota += (f" En {enumerar(parciales['mes'].tolist())} hay menos plantas con costos completos que las elegidas, "
                 "así que esos puntos no comparan exactamente el mismo grupo de plantas.")
    st.caption(nota)

    # Corte por planta
    st.subheader(f"Por planta: costo y sobrecosto referencial, {inicio['mes']} frente a {fin['mes']}")
    por_planta = m.por_planta(df, ley, inicio["anio_mes"], fin["anio_mes"]).sort_values(
        "sobrecosto_clp", ascending=False, na_position="last"
    )
    por_planta["planta"] = por_planta["planta"].map(nombre_planta)
    p1, p2 = st.columns([1.1, 1], gap="large")
    with p1:
        barras = pd.concat([
            por_planta.assign(momento=inicio["mes"], valor=por_planta["costo_inicial"]),
            por_planta.assign(momento=fin["mes"], valor=por_planta["costo_final"]),
        ]).dropna(subset=["valor"])
        barras["valor_txt"] = barras["valor"].map(lambda v: f"{m.formato(v)} USD/lb")
        grafico_plantas = alt.Chart(barras).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("planta:N", sort=por_planta["planta"].tolist(), title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("momento:N", sort=[inicio["mes"], fin["mes"]], scale=alt.Scale(paddingInner=0.04)),
            y=alt.Y("valor:Q", title="USD por libra", scale=alt.Scale(zero=True),
                    axis=alt.Axis(labelExpr=eje_decimal(1), gridColor=GRILLA)),
            color=alt.Color("momento:N", sort=[inicio["mes"], fin["mes"]],
                            scale=alt.Scale(domain=[inicio["mes"], fin["mes"]], range=[AZUL_CLARO, AZUL]),
                            legend=alt.Legend(title=None, orient="top", direction="horizontal")),
            tooltip=[alt.Tooltip("planta:N", title="Planta"), alt.Tooltip("momento:N", title="Mes"),
                     alt.Tooltip("valor_txt:N", title="Costo por libra")],
        ).properties(height=300)
        st.altair_chart(grafico_plantas, width="stretch")
    with p2:
        tabla_plantas = pd.DataFrame({
            "Planta": por_planta["planta"],
            f"{inicio['mes']} (USD/lb)": por_planta["costo_inicial"].map(m.formato),
            f"{fin['mes']} (USD/lb)": por_planta["costo_final"].map(m.formato),
            "Variación": por_planta["variacion"].map(porcentaje),
            "Sobrecosto referencial (MM CLP)": por_planta["sobrecosto_clp"].map(lambda v: m.formato(v / 1e6, 0)),
        })
        st.dataframe(tabla_plantas, hide_index=True, width="stretch")
        primera = por_planta.dropna(subset=["sobrecosto_clp"]).head(1)
        if len(primera) and inicio["anio_mes"] != fin["anio_mes"]:
            p = primera.iloc[0]
            total = por_planta["sobrecosto_clp"].sum()
            st.markdown(
                f"La planta con mayor sobrecosto referencial es {p['planta']}, con {m.formato(p['sobrecosto_clp'] / 1e6, 0)} "
                f"millones de pesos en {fin['mes']}, de un total de {m.formato(total / 1e6, 0)} millones "
                "entre las plantas elegidas."
            )
        st.caption(
            f"El sobrecosto referencial es lo que costó producir las libras finas de {fin['mes']} frente a lo que habrían "
            f"costado al costo por libra en pesos de {inicio['mes']} de la misma planta. Va en pesos para que "
            "el tipo de cambio no lo mueva."
        )

    # Detalle
    st.subheader("Detalle por planta y mes")
    col_libras = m.DEFINICIONES[ley].columna_libras
    detalle = pd.DataFrame({
        "Mes": df["anio_mes"].map(m.nombre_mes),
        "Planta": df["planta_nombre"].map(nombre_planta),
        "Costo directo (MM CLP)": (df["costo_directo_clp"] / 1e6).map(lambda v: m.formato(v, 0)),
        "Dólar (CLP/USD)": df["tc_clp_usd"].map(lambda v: m.formato(v, 2)),
        "Costo directo (miles USD)": (df["costo_directo_usd"] / 1e3).map(lambda v: m.formato(v, 0)),
        "Libras finas (miles)": (df[col_libras] / 1e3).map(lambda v: m.formato(v, 0)),
        "Costo por libra (USD/lb)": (df["costo_directo_usd"] / df[col_libras]).map(m.formato),
        "Precio del cobre (USD/lb)": df["precio_cobre_usd_lb"].map(m.formato),
        "Lotes": df["n_lotes"].map(lambda v: m.formato(v, 0)),
    })
    st.dataframe(detalle, hide_index=True, width="stretch", height="auto" if len(detalle) <= 12 else 420)
    st.caption(f"Las libras finas y el costo por libra de esta tabla usan la definición elegida arriba ({m.DEFINICIONES[ley].etiqueta}).")

# ---------------------------------------------------------------- pestaña 2
with tab_leyes:
    st.subheader("La misma cifra con las tres leyes")
    st.info("Para ver toda la pantalla con otra ley, cámbiala en el selector "
            "«Ley con que se calcula el cobre fino», arriba a la derecha.", icon=":material/tune:")
    st.markdown(
        "Las tres leyes usan los mismos lotes, los mismos costos y el mismo dólar. Sólo cambia con qué ley "
        "se calcula el cobre fino de cada lote, así que la diferencia entre filas es el efecto de la ley."
    )
    principal = m.costo_por_libra(df, m.PRINCIPAL)
    filas = []
    for clave in corrida.definiciones:
        ini_ley, fin_ley = extremos(m.por_mes(df, corrida.dim_mes, clave, mes_inicial, mes_final))
        valor = m.costo_por_libra(df, clave)
        filas.append({
            "Ley": m.DEFINICIONES[clave].etiqueta,
            f"Costo por libra, {etiqueta_periodo} (USD/lb)": m.formato(valor, 4),
            "Diferencia con Operaciones (USD/lb)": m.formato(valor - principal, 4, signo=True),
            "Diferencia con Operaciones (%)": f"{m.formato(100 * (valor / principal - 1), 2, signo=True)} %",
            f"Variación {ini_ley['mes']} a {fin_ley['mes']}":
                porcentaje(variacion(ini_ley["costo_por_libra"], fin_ley["costo_por_libra"])),
        })
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.markdown("\n".join(f"- **{m.DEFINICIONES[c].etiqueta}.** {m.DEFINICIONES[c].regla}" for c in corrida.definiciones))

    st.subheader("Costo por libra de cada mes con cada ley")
    tablas = {c: m.por_mes(df, corrida.dim_mes, c, mes_inicial, mes_final) for c in corrida.definiciones}
    meses_tabla = pd.DataFrame({"Mes": tablas[m.PRINCIPAL]["mes"]})
    for clave, tabla in tablas.items():
        meses_tabla[f"{m.DEFINICIONES[clave].etiqueta} (USD/lb)"] = tabla["costo_por_libra"].map(lambda v: m.formato(v, 4))
    meses_tabla["Plantas con costo"] = tablas[m.PRINCIPAL]["plantas"].astype(str)
    st.dataframe(meses_tabla, hide_index=True, width="stretch")

    alternativas = [c for c in corrida.definiciones if c != m.PRINCIPAL]
    if alternativas:
        colores = {"hibrida": AQUA, "simple": VIOLETA}
        dif = pd.concat([
            tablas[c].assign(
                ley=m.DEFINICIONES[c].etiqueta,
                diferencia=tablas[c]["costo_por_libra"] - tablas[m.PRINCIPAL]["costo_por_libra"],
            )
            for c in alternativas
        ])
        dif["diferencia_txt"] = dif["diferencia"].map(lambda v: f"{m.formato(v, 4, signo=True)} USD/lb")
        st.subheader("Diferencia con la ley de Operaciones, mes a mes")
        grafico_dif = alt.Chart(dif).mark_bar(cornerRadius=3).encode(
            x=alt.X("mes:N", sort=tablas[m.PRINCIPAL]["mes"].tolist(), title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("ley:N", scale=alt.Scale(paddingInner=0.08)),
            y=alt.Y("diferencia:Q", title="USD por libra", axis=alt.Axis(labelExpr=eje_decimal(3), gridColor=GRILLA)),
            color=alt.Color("ley:N", scale=alt.Scale(
                domain=[m.DEFINICIONES[c].etiqueta for c in alternativas],
                range=[colores[c] for c in alternativas]),
                legend=alt.Legend(title=None, orient="top", direction="horizontal", labelLimit=0)),
            tooltip=[alt.Tooltip("mes:N", title="Mes"), alt.Tooltip("ley:N", title="Ley"),
                     alt.Tooltip("diferencia_txt:N", title="Diferencia")],
        ).properties(height=280)
        st.altair_chart(grafico_dif, width="stretch")
        st.caption("Una barra sobre cero significa que esa ley da un costo por libra más alto que la de Operaciones.")

# ---------------------------------------------------------------- pie
st.divider()
api = corrida.estado_api or {}
respaldo = [nombre for nombre, estado in api.items() if estado.get("fuente") != "API"]
if not api:
    estado_api = "La corrida no dejó registro de si el dólar y el cobre vinieron de la API o del respaldo."
elif respaldo:
    estado_api = (f"El dólar y el cobre de esta corrida salen del respaldo guardado en el repositorio "
                  f"({', '.join(respaldo)}), porque la API de mindicador.cl no respondió.")
else:
    estado_api = "El dólar y el cobre de esta corrida se descargaron de la API de mindicador.cl."
if respaldo:
    st.warning(estado_api, icon=":material/cloud_off:")
st.markdown(
    f"""
    <div class="pie">
    <b>Fuente:</b> {m.FUENTES}. {estado_api if not respaldo else ''}<br>
    <b>Actualización:</b> corrida del {corrida.id_fecha[6:]}-{corrida.id_fecha[4:6]}-{corrida.id_fecha[:4]}, con la tabla de hechos escrita el
    {corrida.actualizada:%d-%m-%Y} a las {corrida.actualizada:%H:%M}. La pantalla se recarga sola cuando la cadena vuelve a correr.<br>
    <b>Dueño del dato:</b> {m.DUENO_DATO}. La métrica se llama igual y se calcula con la misma fórmula en el informe,
    en el código (src/metrica.py) y en esta pantalla.
    </div>
    """,
    unsafe_allow_html=True,
)
