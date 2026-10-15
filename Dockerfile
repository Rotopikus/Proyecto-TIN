# Mismo entorno que documenta el README: Ubuntu 24.04, Java 17 y Python 3.12.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless python3-venv python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# run.sh reutiliza este .venv si existe, así las dependencias quedan en la imagen.
COPY requirements.txt .
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt

COPY run.sh .
COPY src/ src/
# Un clon hecho en Windows con core.autocrlf trae run.sh con CRLF, y bash no lo ejecuta.
RUN sed -i 's/\r$//' run.sh

# Los datos originales no van en la imagen: se montan en /app/data_original al ejecutar.
CMD ["bash", "run.sh"]
