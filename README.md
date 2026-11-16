
# Proyecto-TIN

## Para ejecutar

### Este procedimiento está pensado para Ubuntu 24.04 en WSL.

### 1. Clonar repositorio

```bash
git clone https://github.com/Rotopikus/Proyecto-TIN.git
```

### 2. Instalar las dependencias del sistema

```bash
sudo apt update
sudo apt install -y openjdk-17-jdk python3-venv python3-pip
```

Verificar las versiones:

```bash
python3 --version
java -version
```

### 3. Preparar los archivos originales

La estructura de entrada esperada es:

```text
Proyecto-TIN/
├── data_original/
│   ├── origen_mina.sqlite
│   ├── origen_costos_planta.csv
│   ├── origen_leyes_laboratorio.json
│   └── respaldo_API/
│       ├── dólar 2025.json
│       ├── dólar 2026.json
│       ├── cobre 2025.json
│       └── cobre 2026.json
├── src/
│   ├── bronze.py
│   ├── silver.py
│   ├── gold.py
│   ├── tests_silver.py
│   ├── tests_gold.py
│   └── metrica.py
├── prototipo/
│   ├── app.py
│   └── requirements.txt
├── raw_data/                       # Bronze: fuentes crudas
│   ├── mina/
│   ├── costos/
│   ├── origen_leyes/
│   └── mindicador/
│       └── <AAAAMMDD>/
│           └── estado_fuentes.json
├── process_data/                   # Silver: datos limpios
│   ├── lotes/
│   ├── plantas/
│   ├── regiones/
│   ├── costos/
│   ├── origen_leyes/
│   ├── dolar/
│   ├── libra_cobre/
│   └── calidad/
│       └── <AAAAMMDD>/
│           └── pruebas_<RUN_ID>.csv
├── gold_data/                      # Gold: modelo dimensional
│   ├── dim_mes/
│   ├── dim_planta/
│   ├── fact_costo_produccion_mensual/
│   └── calidad/
│       └── <AAAAMMDD>/
│           └── pruebas_<RUN_ID>.csv
├── requirements.txt
├── Dockerfile
├── prototipo.sh
├── README.md
└── run.sh
```

### 4. Ejecutar el código

```bash
bash run.sh
```

## Alternativa: ejecutar con Docker

Funciona igual en Windows, macOS y Linux, sin instalar Java ni Python: sólo hace falta Docker. La imagen reproduce el entorno de arriba (Ubuntu 24.04, OpenJDK 17 y Python 3.12) y ejecuta el mismo `run.sh`.

1. Copiar los datos de minería grupo 3 a `data_original/`, igual que en el paso 3.
2. Desde la raíz del repositorio, construir la imagen y ejecutar la cadena.

macOS o Linux:

```bash
docker build -t proyecto-tin .
docker run --rm -v "$PWD/data_original:/app/data_original:ro" -v "$PWD/raw_data:/app/raw_data" -v "$PWD/process_data:/app/process_data" -v "$PWD/gold_data:/app/gold_data" proyecto-tin
```

Windows (PowerShell):

```powershell
docker build -t proyecto-tin .
docker run --rm -v "${PWD}/data_original:/app/data_original:ro" -v "${PWD}/raw_data:/app/raw_data" -v "${PWD}/process_data:/app/process_data" -v "${PWD}/gold_data:/app/gold_data" proyecto-tin
```

La ejecución genera los archivos originales de Bronze en raw_data/, los datos depurados de Silver en process_data/ y el modelo dimensional Gold en gold_data/. Cada carga se almacena en una carpeta identificada por su fecha de ejecución.

Al final, `run.sh` imprime con `src/metrica.py` las cifras del informe, que son el costo directo por libra del año con las tres leyes, la serie mensual y el corte por planta, las mismas que muestra el prototipo.

### 5. Tiempo de ejecución

En las pruebas realizadas con WSL y Docker, la cadena ha tardado aproximadamente 18 a 41 segundos cuando las consultas a las fuentes responden normalmente o se resuelven rápidamente mediante respaldo.

El tiempo depende del equipo, la inicialización de Spark y la disponibilidad de mindicador.cl. Una API lenta puede prolongar la ejecución por los tiempos de espera y reintentos.

El tiempo final aparece en la consola:

```
==> ELT completado en XX segundos.
Bronze: raw_data/
Silver: process_data/
Gold: gold_data/
```


### 6. Resultados esperados

Con los datos del caso CuprumAndes SpA, la ejecución debe generar:

| Indicador | Resultado esperado |
|---|---:|
| Lotes originales | 14.609 |
| Lotes limpios en Silver | 14.110 |
| Lotes incluidos en el KPI | 12.898 |
| Lotes excluidos del KPI | 1.711 (11,71%) |
| Pares planta-mes válidos | 44 de 48 |
| Registros de `dim_mes` | 12 |
| Registros de `dim_planta` | 4 |
| Registros de `fact_costo_produccion_mensual` | 44 |
| Pruebas Silver aprobadas | 4 de 4 |
| Pruebas Gold aprobadas | 4 de 4 |

**Costo directo de planta por libra de cobre fino (E2):**

| Definición | Resultado esperado |
|---|---:|
| Ley de Operaciones | 2,5642 USD/lb |
| Ley híbrida con Laboratorio | 2,5661 USD/lb |
| Promedio simple de la ley | 2,5646 USD/lb |

Estas cifras corresponden al procesamiento de 2025 utilizando el **último dólar observado disponible de cada mes**, en lugar del promedio mensual utilizado en la E1.

El indicador principal debe mostrar aproximadamente:

- Enero de 2025: 2,017 USD/lb.
- Diciembre de 2025: 3,719 USD/lb.

Los resultados se calculan con los datos disponibles de cada período. Los pares planta-mes con costos incompletos se excluyen, sin imputar los valores faltantes.

Los resultados pueden cambiar si se modifican las fuentes o las reglas de transformación. Cualquier diferencia respecto de estas cifras de referencia debe revisarse y explicarse.

### 7. Verificación de calidad y reproducibilidad

Cada ejecución realiza ocho pruebas automatizadas, cuatro en Silver y cuatro en Gold.

**Pruebas Silver:**

| Prueba | Qué verifica |
|---|---|
| `sqlite_lotes_unicos` | Identificadores de lotes únicos y no nulos |
| `csv_plantas_reconocidas` | Correspondencia de las plantas de costos con SQLite |
| `json_laboratorio_valido` | Identificadores y leyes válidas de laboratorio |
| `api_datos_validos` | Fechas, valores y cobertura mensual de dólar y cobre |

**Pruebas Gold:**

| Prueba | Qué verifica |
|---|---|
| `gold_clave_hechos` | Unicidad de la combinación planta-mes |
| `gold_integridad_referencial` | Claves válidas y sin registros huérfanos |
| `gold_rangos_validos` | Valores de costos y producción válidos |
| `gold_periodo_2025` | Registros dentro del período de análisis |

Los resultados se guardan en:

```text
process_data/calidad/<AAAAMMDD>/pruebas_<RUN_ID>.csv
gold_data/calidad/<AAAAMMDD>/pruebas_<RUN_ID>.csv
```

Cada registro informa qué se verifica, si la prueba pasó o falló, los registros afectados, la acción ante una falla y su detalle.

Las cuatro pruebas Gold se ejecutan sobre los datos construidos en memoria, antes de escribir las tablas definitivas.

La cadena utiliza cargas completas con reemplazo de resultados. Se comprobó que dos ejecuciones con las mismas entradas producen las mismas claves, registros y valores de las tres tablas dimensionales, sin duplicaciones.


## Prototipo

Una pantalla en Streamlit que responde la pregunta del grupo con la última corrida de la cadena. Se abre con:

```bash
bash prototipo.sh
```

Queda en <http://localhost:8501>. La primera vez crea `.venv-prototipo/` e instala `prototipo/requirements.txt`. Pide Python 3.10 o superior y no necesita Java. Si todavía no existe `gold_data/`, hay que correr antes la cadena (`bash run.sh` o Docker).

- Lee la corrida más reciente de `gold_data/`, que es la fecha más alta con las tres tablas. Para leer otra carpeta se usa `TIN_DATOS=/ruta/a/los/datos bash prototipo.sh`.
- Se actualiza solo, ya que cada 10 segundos revisa si la cadena reescribió la tabla de hechos y, si cambió, vuelve a cargar la pantalla.
- La métrica sale de `src/metrica.py`, el mismo módulo que imprime las cifras del informe, por lo que el prototipo no tiene una fórmula propia.
- El período, las plantas, la ley y la pestaña quedan en la URL, así que un estado se comparte con un enlace, por ejemplo `http://localhost:8501/?ley=Promedio+simple+de+la+ley`.

### Lo que el prototipo lee de la cadena

| Archivo | Lo que usa |
|---|---|
| `gold_data/fact_costo_produccion_mensual/<AAAAMMDD>/fact_costo_produccion_mensual.parquet` | `planta_key`, `mes_key`, `costo_directo_clp`, `costo_directo_usd`, `n_lotes` y las libras finas de cada ley: `libras_finas_ops`, `libras_finas_hibridas`, `libras_finas_simple` |
| `gold_data/dim_mes/<AAAAMMDD>/dim_mes.parquet` | `mes_key`, `anio_mes`, `tc_clp_usd`, `precio_cobre_usd_lb` |
| `gold_data/dim_planta/<AAAAMMDD>/dim_planta.parquet` | `planta_key`, `planta_nombre` |
| `raw_data/mindicador/<AAAAMMDD>/estado_fuentes.json` (opcional) | si el dólar y el cobre vinieron de la API o del respaldo, para el aviso del pie |
| `raw_data/mina/<AAAAMMDD>/origen_mina.sqlite` (opcional) | el total de lotes originales, para el porcentaje excluido |

- Una fila de la tabla de hechos es una planta en un mes, y sólo entran los pares con los tres costos completos.
- El costo en USD llega convertido desde la capa oro. El prototipo no convierte, así que la regla del dólar se cambia sólo en `gold.py`.
- Si falta la columna de libras de una ley, esa ley sale del selector y la pantalla lo avisa.
- Las tres tablas tienen que venir de la misma corrida, o sea de la misma carpeta de fecha.
