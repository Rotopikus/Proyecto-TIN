
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




