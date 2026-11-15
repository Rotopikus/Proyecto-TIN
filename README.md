
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
│   └── gold.py
├── raw_data/              # Bronze: fuentes crudas
├── process_data/          # Silver: Parquet limpios
├── gold_data/             # Gold: modelo dimensional
│   ├── dim_mes/
│   ├── dim_planta/
│   └── fact_costo_produccion_mensual/
├── requirements.txt
├── Dockerfile
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




