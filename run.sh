#!/usr/bin/env bash
# Ejecuta la cadena de extracción y procesamiento del proyecto.
# Compatible con Bash en Linux, macOS y Windows mediante WSL2.
set -Eeuo pipefail

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    printf "ERROR: para Windows utiliza Ubuntu en WSL2, no Git Bash/Cygwin.\n" >&2
    exit 1
    ;;
esac

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Uso:
  bash run.sh            Comprueba entradas, prepara .venv y ejecuta la cadena.
  bash run.sh --check    Comprueba requisitos y archivos sin instalar ni ejecutar.
  bash run.sh --help     Muestra esta ayuda.

Requiere Python 3.10-3.12, Java 17, Bash y acceso a internet para
instalar dependencias y consultar mindicador.cl.

Si tienes varias versiones de Python: PYTHON_BIN=python3.12 bash run.sh
En Windows se recomienda ejecutar desde Ubuntu en WSL2.
USAGE
}

MODE="run"
case "${1:-}" in
  "") ;;
  --check) MODE="check" ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; fail "Argumento no reconocido: $1" ;;
esac
if (( $# > 1 )); then usage >&2; fail "Solo se permite un argumento."; fi

for filename in requirements.txt src/bronze.py src/silver.py src/gold.py; do
  [[ -f "$filename" ]] || fail "No existe $filename. Coloca run.sh en la raíz del repositorio."
done

# Los archivos de origen no se incluyen en el repositorio.
inputs=(
  data_original/origen_mina.sqlite
  data_original/origen_costos_planta.csv
  data_original/origen_leyes_laboratorio.json
)
for filename in "${inputs[@]}"; do
  [[ -s "$filename" ]] || fail "Falta o está vacío '$filename'. Copia primero los datos originales a data_original/."
done
log "Archivos originales encontrados (${#inputs[@]})."

# En macOS localizar el JDK 17 instalado, si JAVA_HOME no está definido.
if [[ "$(uname -s)" == "Darwin" && -z "${JAVA_HOME:-}" && -x /usr/libexec/java_home ]]; then
  JAVA_HOME="$(/usr/libexec/java_home -v 17 2>/dev/null)" || true
  if [[ -n "$JAVA_HOME" ]]; then export JAVA_HOME; fi
fi

if [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/java" ]]; then
  JAVA_CMD="$JAVA_HOME/bin/java"
else
  JAVA_CMD="$(command -v java || true)"
fi
[[ -n "$JAVA_CMD" ]] || fail "No se encontró Java. Instala OpenJDK 17 y revisa JAVA_HOME/PATH."
JAVA_VERSION="$("$JAVA_CMD" -version 2>&1 | head -n 1)" || fail "No se pudo ejecutar Java."
if [[ "$JAVA_VERSION" != *'"17.'* && "$JAVA_VERSION" != *'"17"'* ]]; then
  fail "Este proyecto se configura con Java 17; se encontró: $JAVA_VERSION"
fi
log "Java: $JAVA_VERSION"

VENV_PY="$PROJECT_ROOT/.venv/bin/python"
if [[ -x "$VENV_PY" ]]; then
  SELECTED_PY="$VENV_PY"
else
  SELECTED_PY="${PYTHON_BIN:-python3}"
  command -v "$SELECTED_PY" >/dev/null 2>&1 || fail "No se encontró $SELECTED_PY. Instala Python 3.10-3.12 y python3-venv."
fi

# PySpark 3.5.3 y las versiones fijadas en requirements.txt: usar Python 3.10-3.12.
"$SELECTED_PY" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' || \
  fail "Versión incompatible: $($SELECTED_PY --version 2>&1). Usa Python 3.10, 3.11 o 3.12."
log "Python: $($SELECTED_PY --version 2>&1)"

if [[ "$MODE" == "check" ]]; then
  log "Comprobaciones correctas. Ejecuta: bash run.sh"
  exit 0
fi

START_SECONDS=$SECONDS
if [[ ! -x "$VENV_PY" ]]; then
  log "Creando entorno virtual .venv..."
  "$SELECTED_PY" -m venv "$PROJECT_ROOT/.venv" || \
    fail "No se pudo crear .venv; instala python3-venv (Ubuntu) y prueba otra vez."
fi

log "Instalando o verificando dependencias de requirements.txt..."
"$VENV_PY" -m pip install -r requirements.txt

# Garantiza que los procesos de Spark usen el mismo Python del entorno virtual.
export PYSPARK_PYTHON="$VENV_PY"
export PYSPARK_DRIVER_PYTHON="$VENV_PY"
export SPARK_LOCAL_IP="${SPARK_LOCAL_IP:-127.0.0.1}"

# Identificador de fecha compartido por las tres capas
RUN_DATE="$($VENV_PY -c 'from datetime import date; print(date.today().strftime("%Y%m%d"))')"

# Ejecutar Bronze, Silver y Gold en orden
for capa in bronze silver tests_silver gold tests_gold; do

    # Verificar que no haya cambiado el día entre etapas
    CURRENT_DATE="$($VENV_PY -c 'from datetime import date; print(date.today().strftime("%Y%m%d"))')"

    [[ "$CURRENT_DATE" == "$RUN_DATE" ]] || \
        fail "La fecha cambió durante la ejecución. Vuelve a ejecutar la cadena."

    log "Ejecutando capa ${capa}..."
    "$VENV_PY" -u "src/${capa}.py"

done

log "ELT completado en $((SECONDS - START_SECONDS)) segundos."

printf 'Bronze: raw_data/\n'
printf 'Silver: process_data/\n'
printf 'Gold: gold_data/\n'
