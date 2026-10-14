"""Actualización opcional: descarga fuentes públicas, sin modificar los originales remotos."""
from pathlib import Path
from urllib.request import Request,urlopen
import json
P=Path(__file__).resolve().parent
(P/'inputs').mkdir(exist_ok=True)
BASE='https://raw.githubusercontent.com/LMD18/IIC3752-2026-2-Proyecto-Semestral/main/casos/mineria_cobre/grupo_3/'
urls={'mina.sqlite':BASE+'origen_mina.sqlite','inputs/origen_costos_planta.csv':BASE+'origen_costos_planta.csv','inputs/origen_leyes_laboratorio.json':BASE+'origen_leyes_laboratorio.json','dolar.json':'https://mindicador.cl/api/dolar/2025','cobre.json':'https://mindicador.cl/api/libra_cobre/2025'}
for target,url in urls.items():
    candidates=[url]
    if 'mindicador.cl' in url:candidates += [url.replace('https://mindicador.cl','http://www.mindicador.cl'),url.replace('https://mindicador.cl','http://mindicador.cl')]
    for candidate in candidates:
        try:
            data=urlopen(Request(candidate,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
            if target in ['dolar.json','cobre.json']:
                payload=json.loads(data)
                if not payload.get('serie'):raise ValueError('La API no devolvió una serie no vacía')
            (P/target).write_bytes(data);print(target,len(data));break
        except Exception as e:
            if candidate==candidates[-1]:raise RuntimeError(f'No se pudo actualizar {target}; la instantánea previa no se ha sobrescrito') from e
