
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
│    ├── origen_mina.sqlite
│    ├── origen_costos_planta.csv
│    └── origen_leyes_laboratorio.json
├── src/
│   ├── bronze.py
│   ├── silver.py
│   ├── gold.py
│   └── metrica.py         # Capa semántica: nombre, fórmula y leyes de la métrica
├── prototipo/
│   ├── app.py             # Pantalla en Streamlit
│   └── requirements.txt
├── raw_data/              # Bronze: fuentes crudas
├── process_data/          # Silver: Parquet limpios
├── gold_data/             # Gold: modelo dimensional
│   ├── dim_mes/
│   ├── dim_planta/
│   └── fact_costo_produccion_mensual/
├── requirements.txt
├── Dockerfile
├── prototipo.sh
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
