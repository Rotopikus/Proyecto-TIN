
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

### 3. Crear y activar el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar las dependencias del proyecto

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Preparar los archivos originales

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

### 6. Ejecutar la extracción

```bash
python src/extraccion.py
```

### 7. Ejecutar el procesamiento de datos

```bash
python src/process.py
```




