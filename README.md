
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
│   └── origen_leyes_laboratorio.json
├── src/
│   ├── extraccion.py
│   └── process.py
└── requirements.txt
```
Recuerda subir los archivos de datos de minería grupo 3 a la carpeta data_original.

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
docker run --rm -v "$PWD/data_original:/app/data_original:ro" -v "$PWD/raw_data:/app/raw_data" -v "$PWD/graficos:/app/graficos" proyecto-tin
```

Windows (PowerShell):

```powershell
docker build -t proyecto-tin .
docker run --rm -v "${PWD}/data_original:/app/data_original:ro" -v "${PWD}/raw_data:/app/raw_data" -v "${PWD}/graficos:/app/graficos" proyecto-tin
```

Los gráficos quedan en `graficos/` y la extracción en `raw_data/`, igual que con `bash run.sh`. Sigue haciendo falta internet para consultar mindicador.cl.




