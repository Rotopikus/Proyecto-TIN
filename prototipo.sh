#!/usr/bin/env bash
# Abre el prototipo sobre la última corrida de la cadena (gold_data/).
# Usa su propio entorno (.venv-prototipo) para no tocar el .venv de Spark que crea run.sh.
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

VENV="${PROTOTIPO_VENV:-$PROJECT_ROOT/.venv-prototipo}"
if [[ ! -x "$VENV/bin/python" ]]; then
  printf '==> Creando %s...\n' "$VENV"
  "${PYTHON_BIN:-python3}" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q --disable-pip-version-check -r prototipo/requirements.txt

if [[ ! -d "${TIN_DATOS:-$PROJECT_ROOT}/gold_data/fact_costo_produccion_mensual" ]]; then
  printf 'AVISO: todavía no hay capa oro. Corre la cadena (bash run.sh o Docker) y la pantalla la toma sola.\n' >&2
fi

exec "$VENV/bin/streamlit" run prototipo/app.py "$@"
