# Soporte reproducible del ítem E

CuprumAndes SpA, Grupo 11 del curso, Minería set 3. Período: enero a diciembre de 2025.
El informe fue actualizado el 14 de octubre de 2026.

## Reproducir las cifras del informe

Este complemento usa Python y no requiere Spark. Puede ejecutarse en macOS, Linux o Windows.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analisis_e.py
python graficos_e.py
```

En Windows, activar con `.venv\Scripts\activate`.
La ejecución de los cálculos y figuras tarda aproximadamente 5 segundos en el entorno de elaboración; la instalación depende del equipo.

La ejecución por defecto usa las cinco entradas incluidas, con las series de la API congeladas al 14-10-2026. Esto evita que una caída de la API impida reproducir las cifras.
Para actualizar las fuentes desde sus sitios originales, ejecutar `python descargar_fuentes.py` y luego ambos scripts. La actualización puede cambiar las cifras si cambia la fuente; no cambia archivos remotos.

## Salidas esperadas

- `resultados/planta_mes.csv`: 44 pares planta-mes, costos, producción y ambas definiciones.
- `resultados/mensual.csv`: 12 meses, cobertura, precio del cobre y dólar.
- `resultados/cobertura_lotes.csv`: trazabilidad de las 14.609 filas de origen y motivo final.
- `resultados/lotes_preparados.csv`: lotes válidos antes de excluir los pares sin costos completos.
- `resultados/caso_negocio.csv` y `hallazgos.json`: cálculo del impacto en pesos y de cada afirmación central.
- `resultados/resumen.json`: conciliación con el cálculo original, controles y sensibilidad a duplicados.
- `graficos/figura_2.png`, `figura_3.png`, `figura_4.png`: tres gráficos del ítem E.
- `graficos/figuras_3_4.png`: composición de las figuras 3 y 4 usada en Word.

Resultados: costo agregado 2,558280 USD/lb (Operaciones) y 2,560141 USD/lb (híbrido); 12.898 filas incluidas; 1.711 excluidas (11,71%). Enero: 1,991915 USD/lb. Diciembre: 3,698863 USD/lb. Brecha contra el costo unitario de enero, aplicada al volumen y mezcla de diciembre: CLP 49.364.892.378,23.

## Cambios frente al código original

El archivo `process_original.py` es una copia de referencia del commit `bdd6bc4a8caa8929a354a0a3516ed35d0b75f8f4` de Rotopikus/Proyecto-TIN; no debe ejecutarse para reproducir el informe corregido.

1. Se normalizan los meses españoles antes de interpretar fechas: se recuperan 1.179 fechas.
2. Se mantiene la exclusión de 72 toneladas con coma, acordada en el informe.
3. Se excluyen 202 filas restantes con ley o recuperación fuera de [0,100]. No se imputan porcentajes.
4. Se conserva la primera fila válida por lote_id, en orden rowid de SQLite: se eliminan 142 duplicados. Usar la última fila cambia el KPI en +0,00021%.
5. Se excluyen del numerador y denominador cuatro pares planta-mes sin costos completos (1.295 filas adicionales): Loa marzo/agosto, Cerro Norte junio y Salado noviembre.
6. Se incorpora el precio mensual del cobre y se exportan las tablas y gráficos.

Las categorías de exclusión son secuenciales y mutuamente excluyentes. Se mantienen los costos completos de los meses incluidos y se utiliza solamente producción válida observada. Por eso el KPI puede sobreestimar el costo unitario si parte de la producción excluida fue real. No se extrapolan los meses faltantes. La cobertura de Laboratorio en los lotes analizados es 6,09%.

Las cifras originales 1,4674 y 1,5090 se reproducen en el escenario `original`; fueron sustituidas en la sección D del informe por las cifras verificadas, con conciliación en el anexo. El repositorio remoto de los compañeros no fue modificado; debe incorporarse este complemento al repositorio de entrega para que el enlace de portada permita reproducir todas las cifras.

## Fuentes

- https://github.com/LMD18/IIC3752-2026-2-Proyecto-Semestral/tree/main/casos/mineria_cobre/grupo_3
- https://github.com/Rotopikus/Proyecto-TIN/tree/bdd6bc4a8caa8929a354a0a3516ed35d0b75f8f4
- https://mindicador.cl/api/dolar/2025
- https://mindicador.cl/api/libra_cobre/2025

Las series se obtuvieron mediante las variantes públicas HTTP de mindicador.cl / www.mindicador.cl cuando la ruta HTTPS devolvió error. Ambas respuestas conservan los metadatos del proveedor. `manifest.json` registra hashes SHA-256 y Git de los archivos usados. El escenario de recuperar un 10% de la brecha de gasto es ilustrativo; no es una meta acordada ni un ahorro garantizado.
