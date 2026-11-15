"""Capa semántica: el nombre, la fórmula y las definiciones de la métrica están aquí.

La consumen el prototipo (prototipo/app.py) y las cifras del informe, que se
imprimen con `python src/metrica.py` al final de run.sh. No recalcula nada que la
cadena ya resolvió: el costo en USD y las libras finas de cada definición vienen
de la tabla de hechos de la capa oro, y aquí sólo se agregan.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

NOMBRE = "Costo directo de planta por libra de cobre fino"
UNIDAD = "USD/lb"
# Cargo dueño del dato según el acuerdo de servicio de la sección B.
DUENO_DATO = "Jefatura de Control de Gestión"
FUENTES = (
    "Base operacional de la mina (lotes, plantas y regiones), "
    "costos de planta de Control de Gestión, leyes de Laboratorio "
    "y mindicador.cl (dólar observado y libra de cobre)"
)


@dataclass(frozen=True)
class Definicion:
    clave: str
    etiqueta: str
    columna_libras: str
    regla: str


DEFINICIONES = {
    "ops": Definicion(
        "ops",
        "Ley de Operaciones",
        "libras_finas_ops",
        "Cada lote se calcula con la ley que reporta Operaciones, que es la definición principal.",
    ),
    "hibrida": Definicion(
        "hibrida",
        "Ley híbrida con Laboratorio",
        "libras_finas_hibridas",
        "Cada lote se calcula con la ley de Laboratorio cuando tiene un ensayo válido, "
        "y con la de Operaciones cuando no lo tiene.",
    ),
    "simple": Definicion(
        "simple",
        "Promedio simple de la ley",
        "libras_finas_simple",
        "Cada lote se calcula con el promedio simple de la ley de Operaciones de su "
        "planta y mes, sin ponderar por tonelaje.",
    ),
}
PRINCIPAL = "ops"

# Contrato con la capa oro: gold_data/<tabla>/<AAAAMMDD>/<tabla>.parquet
TABLA_HECHOS = "fact_costo_produccion_mensual"
COLUMNAS_REQUERIDAS = {
    TABLA_HECHOS: ["planta_key", "mes_key", "costo_directo_clp", "costo_directo_usd", "n_lotes"],
    "dim_mes": ["mes_key", "anio_mes", "tc_clp_usd", "precio_cobre_usd_lb"],
    "dim_planta": ["planta_key", "planta_nombre"],
}

MESES_CORTOS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")

RAIZ_REPO = Path(__file__).resolve().parents[1]


def raiz_datos() -> Path:
    """Carpeta que contiene raw_data/ y gold_data/. Se cambia con TIN_DATOS."""
    return Path(os.environ.get("TIN_DATOS") or RAIZ_REPO)


def formato(valor: float, decimales: int = 3, signo: bool = False) -> str:
    """Número con coma decimal y punto de miles, como se escribe en el informe."""
    if valor is None or pd.isna(valor):
        return "sin dato"
    patron = f"{{:{'+' if signo else ''},.{decimales}f}}"
    return patron.format(valor).replace(",", "_").replace(".", ",").replace("_", ".")


def nombre_mes(anio_mes: str) -> str:
    anio, mes = anio_mes.split("-")
    return f"{MESES_CORTOS[int(mes) - 1]} {anio}"


@dataclass
class Corrida:
    id_fecha: str
    actualizada: datetime
    planta_mes: pd.DataFrame
    dim_mes: pd.DataFrame
    dim_planta: pd.DataFrame
    definiciones: list[str]
    estado_api: dict | None
    lotes_originales: int | None


def _particiones(tabla: str, raiz: Path) -> set[str]:
    carpeta = raiz / "gold_data" / tabla
    if not carpeta.is_dir():
        return set()
    return {p.name for p in carpeta.iterdir() if (p / f"{tabla}.parquet").is_file()}


def ultima_corrida(raiz: Path | None = None) -> str:
    """La fecha de carga más reciente en que la capa oro dejó las tres tablas."""
    raiz = raiz or raiz_datos()
    comunes = set.intersection(*(_particiones(t, raiz) for t in COLUMNAS_REQUERIDAS))
    if not comunes:
        raise FileNotFoundError(
            f"No hay una corrida completa de la capa oro en {raiz / 'gold_data'}. "
            "Ejecuta la cadena con `bash run.sh` (o con Docker) antes de abrir el prototipo."
        )
    return max(comunes)


def firma(raiz: Path | None = None) -> tuple[str, float]:
    """Cambia cada vez que la cadena vuelve a escribir la tabla de hechos."""
    raiz = raiz or raiz_datos()
    id_fecha = ultima_corrida(raiz)
    archivo = raiz / "gold_data" / TABLA_HECHOS / id_fecha / f"{TABLA_HECHOS}.parquet"
    return id_fecha, archivo.stat().st_mtime


def _leer(tabla: str, id_fecha: str, raiz: Path) -> pd.DataFrame:
    df = pd.read_parquet(raiz / "gold_data" / tabla / id_fecha / f"{tabla}.parquet")
    faltan = [c for c in COLUMNAS_REQUERIDAS[tabla] if c not in df.columns]
    if faltan:
        raise ValueError(f"La tabla {tabla} de la corrida {id_fecha} no trae las columnas {faltan}.")
    return df


def _estado_api(id_fecha: str, raiz: Path) -> dict | None:
    archivo = raiz / "raw_data" / "mindicador" / id_fecha / "estado_fuentes.json"
    if not archivo.is_file():
        return None
    return json.loads(archivo.read_text(encoding="utf-8"))


def _lotes_originales(id_fecha: str, raiz: Path) -> int | None:
    archivo = raiz / "raw_data" / "mina" / id_fecha / "origen_mina.sqlite"
    if not archivo.is_file():
        return None
    with sqlite3.connect(f"file:{archivo}?mode=ro", uri=True) as con:
        return con.execute("SELECT COUNT(*) FROM lotes").fetchone()[0]


def cargar_corrida(raiz: Path | None = None, id_fecha: str | None = None) -> Corrida:
    raiz = raiz or raiz_datos()
    id_fecha = id_fecha or ultima_corrida(raiz)
    fact = _leer(TABLA_HECHOS, id_fecha, raiz)
    dim_mes = _leer("dim_mes", id_fecha, raiz).sort_values("anio_mes").reset_index(drop=True)
    dim_planta = _leer("dim_planta", id_fecha, raiz).sort_values("planta_key").reset_index(drop=True)

    definiciones = [c for c, d in DEFINICIONES.items() if d.columna_libras in fact.columns]
    if PRINCIPAL not in definiciones:
        raise ValueError(f"La tabla de hechos no trae {DEFINICIONES[PRINCIPAL].columna_libras}.")

    planta_mes = (
        fact.merge(dim_planta[["planta_key", "planta_nombre"]], on="planta_key", how="left", validate="many_to_one")
        .merge(dim_mes[["mes_key", "anio_mes", "tc_clp_usd", "precio_cobre_usd_lb"]], on="mes_key",
               how="left", validate="many_to_one")
        .sort_values(["anio_mes", "planta_nombre"])
        .reset_index(drop=True)
    )
    archivo = raiz / "gold_data" / TABLA_HECHOS / id_fecha / f"{TABLA_HECHOS}.parquet"
    return Corrida(
        id_fecha=id_fecha,
        actualizada=datetime.fromtimestamp(archivo.stat().st_mtime),
        planta_mes=planta_mes,
        dim_mes=dim_mes,
        dim_planta=dim_planta,
        definiciones=definiciones,
        estado_api=_estado_api(id_fecha, raiz),
        lotes_originales=_lotes_originales(id_fecha, raiz),
    )


# La métrica. No es aditiva: se agrega como razón de sumas, nunca como promedio
# de los costos unitarios de cada planta-mes.

def costo_por_libra(df: pd.DataFrame, definicion: str = PRINCIPAL) -> float:
    libras = df[DEFINICIONES[definicion].columna_libras].sum()
    return df["costo_directo_usd"].sum() / libras if libras else float("nan")


def costo_clp_por_libra(df: pd.DataFrame, definicion: str = PRINCIPAL) -> float:
    libras = df[DEFINICIONES[definicion].columna_libras].sum()
    return df["costo_directo_clp"].sum() / libras if libras else float("nan")


def por_mes(df: pd.DataFrame, dim_mes: pd.DataFrame, definicion: str = PRINCIPAL,
            mes_inicial: str | None = None, mes_final: str | None = None) -> pd.DataFrame:
    """Una fila por mes del período: costo por libra, precio del cobre y brecha entre ambos.

    Un mes sin pares planta-mes con costos completos queda con el costo vacío, no se omite.
    """
    mes_inicial = mes_inicial or df["anio_mes"].min()
    mes_final = mes_final or df["anio_mes"].max()
    meses = dim_mes[dim_mes["anio_mes"].between(mes_inicial, mes_final)]
    filas = []
    for _, mes in meses.iterrows():
        del_mes = df[df["anio_mes"] == mes["anio_mes"]]
        costo = costo_por_libra(del_mes, definicion) if len(del_mes) else float("nan")
        filas.append({
            "anio_mes": mes["anio_mes"],
            "mes": nombre_mes(mes["anio_mes"]),
            "plantas": del_mes["planta_key"].nunique(),
            "costo_por_libra": costo,
            "precio_cobre": mes["precio_cobre_usd_lb"],
            "brecha": mes["precio_cobre_usd_lb"] - costo,
        })
    return pd.DataFrame(filas)


def por_planta(df: pd.DataFrame, definicion: str, mes_inicial: str, mes_final: str) -> pd.DataFrame:
    """Costo por libra de cada planta en el período y en sus dos extremos.

    El sobrecosto es el caso de negocio de la E1, o sea lo que costó producir las libras
    del último mes frente a lo que habrían costado al costo unitario en pesos del
    primer mes de esa misma planta. Va en pesos para no mezclar el tipo de cambio.
    """
    col = DEFINICIONES[definicion].columna_libras
    filas = []
    for (clave, nombre), planta in df.groupby(["planta_key", "planta_nombre"]):
        inicio = planta[planta["anio_mes"] == mes_inicial]
        fin = planta[planta["anio_mes"] == mes_final]
        costo_ini = costo_por_libra(inicio, definicion) if len(inicio) else float("nan")
        costo_fin = costo_por_libra(fin, definicion) if len(fin) else float("nan")
        if len(inicio) and len(fin):
            sobrecosto = fin["costo_directo_clp"].sum() - costo_clp_por_libra(inicio, definicion) * fin[col].sum()
        else:
            sobrecosto = float("nan")
        filas.append({
            "planta_key": clave,
            "planta": nombre,
            "costo_por_libra": costo_por_libra(planta, definicion),
            "costo_inicial": costo_ini,
            "costo_final": costo_fin,
            "variacion": costo_fin / costo_ini - 1,
            "sobrecosto_clp": sobrecosto,
            "costo_usd": planta["costo_directo_usd"].sum(),
            "libras": planta[col].sum(),
        })
    return pd.DataFrame(filas)


def cobertura(corrida: Corrida, df: pd.DataFrame, mes_inicial: str, mes_final: str, plantas: int) -> dict:
    """Cuántos pares planta-mes y cuántos lotes entran en la cifra.

    Los lotes originales sólo se cuentan para la empresa completa en el año completo,
    porque la capa cruda no los separa por planta ni por mes válido.
    """
    meses = int(corrida.dim_mes["anio_mes"].between(mes_inicial, mes_final).sum())
    completa = meses == len(corrida.dim_mes) and plantas == len(corrida.dim_planta)
    return {
        "pares": len(df),
        "pares_posibles": meses * plantas,
        "lotes": int(df["n_lotes"].sum()),
        "lotes_originales": corrida.lotes_originales if completa else None,
    }


def _imprimir_cifras(corrida: Corrida) -> None:
    df = corrida.planta_mes
    principal = costo_por_libra(df, PRINCIPAL)
    cob = cobertura(corrida, df, corrida.dim_mes["anio_mes"].min(), corrida.dim_mes["anio_mes"].max(),
                    len(corrida.dim_planta))
    print(f"\n{NOMBRE} ({UNIDAD})")
    print(f"Corrida {corrida.id_fecha}, tabla de hechos escrita el {corrida.actualizada:%d-%m-%Y %H:%M}")
    print(f"{cob['pares']} de {cob['pares_posibles']} pares planta-mes, {formato(cob['lotes'], 0)} lotes", end="")
    if cob["lotes_originales"]:
        excluidos = 1 - cob["lotes"] / cob["lotes_originales"]
        print(f" de {formato(cob['lotes_originales'], 0)} ({formato(100 * excluidos, 2)} % excluidos)")
    else:
        print()

    print("\nPeríodo completo")
    for clave in corrida.definiciones:
        valor = costo_por_libra(df, clave)
        linea = f"  {DEFINICIONES[clave].etiqueta:<38}{formato(valor, 4)}"
        if clave != PRINCIPAL:
            linea += f"   {formato(valor - principal, 4, signo=True)} ({formato(100 * (valor / principal - 1), 2, signo=True)} %)"
        print(linea)

    print("\nPor mes")
    tablas = {c: por_mes(df, corrida.dim_mes, c) for c in corrida.definiciones}
    encabezado = "".join(f"{c:>10}" for c in corrida.definiciones)
    print(f"  {'mes':<10}{encabezado}{'cobre':>10}{'plantas':>9}")
    base = tablas[PRINCIPAL]
    for i, fila in base.iterrows():
        valores = "".join(f"{formato(tablas[c].loc[i, 'costo_por_libra'], 3):>10}" for c in corrida.definiciones)
        print(f"  {fila['mes']:<10}{valores}{formato(fila['precio_cobre'], 3):>10}{fila['plantas']:>9}")

    inicial, final = base["anio_mes"].iloc[0], base["anio_mes"].iloc[-1]
    print(f"\nPor planta, {nombre_mes(inicial)} frente a {nombre_mes(final)} ({DEFINICIONES[PRINCIPAL].etiqueta})")
    plantas = por_planta(df, PRINCIPAL, inicial, final).sort_values("sobrecosto_clp", ascending=False)
    for _, p in plantas.iterrows():
        print(f"  {p['planta']:<14}{formato(p['costo_inicial'])} -> {formato(p['costo_final'])}"
              f"  ({formato(100 * p['variacion'], 1, signo=True)} %)"
              f"  sobrecosto {formato(p['sobrecosto_clp'] / 1e6, 0)} MM CLP")
    print(f"  {'Total':<14}sobrecosto {formato(plantas['sobrecosto_clp'].sum() / 1e6, 0)} MM CLP")


if __name__ == "__main__":
    _imprimir_cifras(cargar_corrida())
