"""Reproduce el análisis E de CuprumAndes, Minería grupo_3, año 2025.

Entradas locales: mina.sqlite, inputs/origen_costos_planta.csv,
inputs/origen_leyes_laboratorio.json, dolar.json y cobre.json.
Las series API se conservan como evidencia de la consulta del 14-10-2026.
"""
from pathlib import Path
import json, sqlite3, re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'resultados'
OUT.mkdir(exist_ok=True)

def numeric(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '.', regex=False), errors='coerce')

def money(s):
    return pd.to_numeric(s.astype(str).str.replace('$','',regex=False).str.replace('.','',regex=False).str.replace(',','.',regex=False),errors='coerce')

def dates(s):
    mapping={'ene':'jan','abr':'apr','ago':'aug','dic':'dec'}
    t=s.astype(str).str.lower()
    for es,en in mapping.items(): t=t.str.replace(es,en,regex=False)
    return pd.to_datetime(t,format='mixed',dayfirst=True,errors='coerce')

con=sqlite3.connect(ROOT/'mina.sqlite')
raw=pd.read_sql('SELECT rowid AS fila_fuente, * FROM lotes',con)
plantas=pd.read_sql('SELECT * FROM plantas',con)
costos=pd.read_csv(ROOT/'inputs/origen_costos_planta.csv',sep=';',encoding='latin1',dtype=str)
lab=pd.DataFrame(json.loads((ROOT/'inputs/origen_leyes_laboratorio.json').read_text())['registros'])
lab['ley_lab']=numeric(lab['ley_lab_prom'])
assert not lab.lote_id.duplicated().any()

costos=costos[~costos.planta.str.upper().str.strip().isin(['TOTAL','PLANTA'])].copy()
costos['nombre_std']=costos.planta.str.upper().str.strip().str.replace(r'^(PLANTA |P\. )','',regex=True)
plantas['nombre_std']=plantas.nombre.str.upper().str.replace('PLANTA ','',regex=False)
costos=costos.merge(plantas[['planta_id','nombre_std']],on='nombre_std',how='left',validate='many_to_one')
for col in ['energia_clp','insumos_clp','mano_obra_clp']: costos[col]=money(costos[col])
costos['costo_clp']=costos[['energia_clp','insumos_clp','mano_obra_clp']].sum(axis=1,min_count=3)
assert costos.planta_id.notna().all()
assert not costos.duplicated(['planta_id','mes']).any()
costos['valido']=costos.costo_clp.notna()

series=[]
for name,col in [('dolar','tc'),('cobre','precio_cobre')]:
    path=ROOT/f'{name}.json'
    if not path.exists(): continue
    source=json.loads(path.read_text())
    x=pd.DataFrame(source['serie'])
    x['fecha']=pd.to_datetime(x.fecha,utc=True).dt.tz_convert('America/Santiago').dt.tz_localize(None)
    assert not x.fecha.duplicated().any()
    x=x[x.fecha.dt.year.eq(2025)].copy()
    x['mes']=x.fecha.dt.strftime('%Y-%m')
    x.to_csv(OUT/f'{name}_diario.csv',index=False)
    m=x.groupby('mes').valor.agg(['mean','count']).rename(columns={'mean':col,'count':f'n_{name}'})
    series.append(m)
macro=pd.concat(series,axis=1)

def prepare(mode,keep_duplicate='first'):
    x=raw.copy()
    x['fecha_calculo']=dates(x.fecha) if mode in ['fechas','final'] else pd.to_datetime(x.fecha,format='mixed',dayfirst=True,errors='coerce')
    x['mes_calculo']=x.fecha_calculo.dt.strftime('%Y-%m')
    x['ton_ambigua']=x.toneladas_tratadas.astype(str).str.contains(',',regex=False)
    x['ton']=pd.to_numeric(x.toneladas_tratadas.astype(str).str.replace('.','',regex=False),errors='coerce')
    x['ley']=numeric(x.ley_pct);x['rec']=numeric(x.recuperacion_pct)
    x['motivo']='incluido'
    x.loc[x.ton_ambigua,'motivo']='tonelaje ambiguo'
    x.loc[x.motivo.eq('incluido') & x.fecha_calculo.isna(),'motivo']='fecha no interpretada'
    if mode=='final':
        invalid=(~x.ley.between(0,100)) | (~x.rec.between(0,100)) | x.ton.le(0)
        x.loc[x.motivo.eq('incluido') & invalid,'motivo']='ley o recuperacion fuera de rango'
        # La fuente no trae sello de actualización. Se conserva la primera fila
        # válida de cada lote_id según rowid, y se mide la alternativa última.
        dup=x.loc[x.motivo.eq('incluido'),'lote_id'].duplicated(keep=keep_duplicate)
        x.loc[dup[dup].index,'motivo']='duplicado de lote_id'
    valid=x[x.motivo.eq('incluido')].copy()
    assert valid[['ton','ley','rec']].notna().all().all()
    if mode=='final': assert ((valid.ton>0)&valid.ley.between(0,100)&valid.rec.between(0,100)).all()
    valid=valid.merge(lab[['lote_id','ley_lab']],on='lote_id',how='left',validate='many_to_one')
    valid['ley_hib']=valid.ley_lab.fillna(valid.ley)
    valid['lb_ops']=valid.ton*valid.ley/100*valid.rec/100*1000/0.45359237
    valid['lb_hib']=valid.ton*valid.ley_hib/100*valid.rec/100*1000/0.45359237
    prod=valid.groupby(['planta_id','mes_calculo']).agg(lb_ops=('lb_ops','sum'),lb_hib=('lb_hib','sum'),ton=('ton','sum'),n_lotes=('lote_id','count'),n_lab=('ley_lab','count')).reset_index().rename(columns={'mes_calculo':'mes'})
    cs=costos.copy()
    if mode=='original':cs['costo_clp']=cs.costo_clp.fillna(0)
    else:cs=cs[cs.valido].copy()
    f=prod.merge(cs[['planta_id','mes','energia_clp','insumos_clp','mano_obra_clp','costo_clp']],on=['planta_id','mes'],how='inner',validate='one_to_one').merge(macro,on='mes',how='inner',validate='many_to_one')
    f=f.merge(plantas[['planta_id','nombre']],on='planta_id',validate='many_to_one')
    f['costo_usd']=f.costo_clp/f.tc
    f['c_ops']=f.costo_usd/f.lb_ops;f['c_hib']=f.costo_usd/f.lb_hib;f['c_clp']=f.costo_clp/f.lb_ops
    result={'filas':len(f),'c_ops':f.costo_usd.sum()/f.lb_ops.sum(),'c_hib':f.costo_usd.sum()/f.lb_hib.sum(),'lb':f.lb_ops.sum()}
    if mode=='final' and keep_duplicate=='first':
        keys=set(zip(f.planta_id,f.mes))
        no_cost=x.motivo.eq('incluido') & pd.Series([k not in keys for k in zip(x.planta_id,x.mes_calculo)],index=x.index)
        x.loc[no_cost,'motivo']='planta mes sin costo completo'
        x[['fila_fuente','lote_id','planta_id','fecha','mes_calculo','motivo']].to_csv(OUT/'cobertura_lotes.csv',index=False)
        valid.to_csv(OUT/'lotes_preparados.csv',index=False)
        result['cobertura']=x.motivo.value_counts().to_dict()
        result['n_lab']=int(f.n_lab.sum())
        result['n_lotes']=int(f.n_lotes.sum())
    return f,result

summary={}
for mode in ['original','costos','fechas','final']:
    frame,summary[mode]=prepare(mode)
    if mode=='final':f=frame
    print(mode,summary[mode])
f.to_csv(OUT/'planta_mes.csv',index=False)
monthly=f.groupby('mes').agg(costo_usd=('costo_usd','sum'),costo_clp=('costo_clp','sum'),lb_ops=('lb_ops','sum'),lb_hib=('lb_hib','sum'),ton=('ton','sum'),n_lotes=('n_lotes','sum'),n_lab=('n_lab','sum'),n_plantas=('planta_id','nunique'),energia=('energia_clp','sum'),insumos=('insumos_clp','sum'),mano_obra=('mano_obra_clp','sum'))
monthly=monthly.join(macro)
monthly['c_ops']=monthly.costo_usd/monthly.lb_ops;monthly['c_hib']=monthly.costo_usd/monthly.lb_hib;monthly['c_clp']=monthly.costo_clp/monthly.lb_ops
monthly['c_tc_enero']=monthly.c_clp/monthly.tc.iloc[0]
if 'precio_cobre' in monthly:monthly['brecha']=monthly.precio_cobre-monthly.c_ops
monthly.to_csv(OUT/'mensual.csv')
print(monthly.to_string())
summary['pares_excluidos']=[{'planta_id':p,'mes':m} for p in plantas.planta_id for m in macro.index if (p,m) not in set(zip(f.planta_id,f.mes))]
_,last_result=prepare('final',keep_duplicate='last')
summary['duplicado_ultima_fila']=last_result
summary['delta_duplicados_pct']=(last_result['c_ops']/summary['final']['c_ops']-1)*100
summary['fechas_recuperadas']=int(dates(raw.fecha).notna().sum()-pd.to_datetime(raw.fecha,format='mixed',dayfirst=True,errors='coerce').notna().sum())
summary['raw_n']=len(raw)
summary['assertions']={'44_pares':len(f)==44,'lotes_finales':int(f.n_lotes.sum())==12898,'reproduccion_original':abs(summary['original']['c_ops']-1.4674)<0.00005,'fechas_todas_validas':bool(dates(raw.fecha).notna().all()),'meses_12':len(monthly)==12}
assert all(summary['assertions'].values())
(OUT/'resumen.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=lambda o: o.item()))

# Hallazgos y escenario económico reproducibles del texto del informe.
a,b=monthly.iloc[0],monthly.iloc[-1]
rows=[]
for name,z in f.groupby('nombre'):
    z=z.set_index('mes');jan,dec=z.loc['2025-01'],z.loc['2025-12']
    rows.append({'planta':name,'costo_enero_usd_lb':jan.c_ops,'costo_diciembre_usd_lb':dec.c_ops,'alza_costo_pct':100*(dec.c_ops/jan.c_ops-1),'alza_costo_clp_pct':100*(dec.costo_clp/jan.costo_clp-1),'cambio_libras_pct':100*(dec.lb_ops/jan.lb_ops-1),'cambio_tonelaje_pct':100*(dec.ton/jan.ton-1),'brecha_diciembre_clp':(dec.c_clp-jan.c_clp)*dec.lb_ops})
case=pd.DataFrame(rows);case.to_csv(OUT/'caso_negocio.csv',index=False)
findings={'comparacion':'enero versus diciembre de 2025, cuatro plantas en ambos meses','alza_costo_usd_pct':100*(b.c_ops/a.c_ops-1),'alza_costo_clp_pct':100*(b.c_clp/a.c_clp-1),'alza_precio_cobre_pct':100*(b.precio_cobre/a.precio_cobre-1),'caida_brecha_pct':100*(b.brecha/a.brecha-1),'brecha_gasto_diciembre_clp':case.brecha_diciembre_clp.sum(),'escenario_recuperacion_10pct_clp':case.brecha_diciembre_clp.sum()*.1,'cobertura_lab_pct':100*summary['final']['n_lab']/summary['final']['n_lotes'],'exclusion_filas_pct':100*(len(raw)-summary['final']['n_lotes'])/len(raw),'puente':{'inicial':a.brecha,'precio':b.precio_cobre-a.precio_cobre,'costo_clp_a_tc_enero':-(b.c_clp-a.c_clp)/a.tc,'dolar':-b.c_clp*(1/b.tc-1/a.tc),'final':b.brecha}}
assert abs(sum(v for k,v in findings['puente'].items() if k!='final')-findings['puente']['final'])<1e-10
(OUT/'hallazgos.json').write_text(json.dumps(findings,indent=2,ensure_ascii=False,default=lambda o:o.item()))
