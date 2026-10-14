from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

P=Path(__file__).resolve().parent
M=pd.read_csv(P/'resultados/mensual.csv',index_col='mes')
F=pd.read_csv(P/'resultados/planta_mes.csv')
OUT=P/'graficos';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,'axes.labelsize':10,'xtick.labelsize':9,'ytick.labelsize':9,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#777777','axes.linewidth':.6,'grid.color':'#dddddd','grid.linewidth':.5,'savefig.dpi':250})
blue='#245475';orange='#A65A24';gray='#707070';light='#BFCED8'
fmt=lambda x,n=2:f'{x:.{n}f}'.replace('.',',')
comma=FuncFormatter(lambda x,pos:fmt(x,1))

fig,ax=plt.subplots(figsize=(6.25,2.55));fig.subplots_adjust(left=.075,right=.98,top=.77,bottom=.24)
fig.text(.02,.96,'Figura 2  Evolución mensual del costo y precio del cobre · USD/lb',ha='left',va='top',weight='bold',fontsize=10)
x=np.arange(12)
ax.plot(x,M.precio_cobre,color=orange,marker='s',ms=3,lw=1.7,label='Precio del cobre')
ax.plot(x,M.c_ops,color=blue,marker='o',ms=3,lw=1.7,label='Costo de planta')
ax.plot(x,M.c_tc_enero,color=gray,ls='--',lw=1.3,label='Costo con dólar de enero')
ax.set_xticks(x,['Ene','Feb','Mar*','Abr','May','Jun*','Jul','Ago*','Sep','Oct','Nov*','Dic'])
ax.set_ylim(0,6);ax.set_yticks([0,2,4,6]);ax.yaxis.set_major_formatter(comma);ax.grid(axis='y');ax.legend(loc='upper left',bbox_to_anchor=(0,1.27),ncol=3,frameon=False,fontsize=8.4,handlelength=1.7,columnspacing=.9)
for idx,col,dy in [(0,'c_ops',-.46),(11,'c_ops',.16),(0,'precio_cobre',.15),(11,'precio_cobre',.17)]:ax.text(idx,M[col].iloc[idx]+dy,fmt(M[col].iloc[idx]),ha='center',fontsize=9,color=blue if col=='c_ops' else orange,weight='bold')
fig.text(.02,.085,'2025. * Tres plantas con costos completos; los demás meses incluyen cuatro.',fontsize=8.1)
fig.text(.02,.025,'Fuente: SQLite y CSV Minería 3; API mindicador.cl, consulta 14-10-2026. Elaboración propia.',fontsize=7.5)
fig.savefig(OUT/'figura_2.png');plt.close(fig)

a=M.iloc[0];b=M.iloc[-1]
values=[a.brecha,b.precio_cobre-a.precio_cobre,-(b.c_clp-a.c_clp)/a.tc,-b.c_clp*(1/b.tc-1/a.tc),b.brecha]
bottom=[0,values[0],values[0]+values[1]+values[2],values[4],0]
heights=[values[0],values[1],-values[2],-values[3],values[4]]
fig,ax=plt.subplots(figsize=(3.1,2.6));fig.subplots_adjust(left=.13,right=.98,top=.76,bottom=.29)
fig.text(.02,.96,'Figura 3  Cambio de la brecha · USD/lb',ha='left',va='top',weight='bold',fontsize=9)
fig.text(.02,.87,'Precio del cobre menos costo de planta',fontsize=8.1)
ax.bar(np.arange(5),heights,bottom=bottom,color=[blue,'#65865A',orange,orange,blue],width=.64)
ax.set_xticks(range(5),['Enero','Precio','Costo\nen CLP','Dólar','Diciembre'],fontsize=8)
ax.set_ylim(0,3.9);ax.set_yticks([0,1,2,3]);ax.yaxis.set_major_formatter(comma);ax.grid(axis='y');ax.set_axisbelow(True)
for i,v in enumerate(values):
 label=fmt(v,2) if i in [0,4] else ('+' if v>0 else '−')+fmt(abs(v),2)
 ax.text(i,bottom[i]+heights[i]+.08,label,ha='center',fontsize=8.4,weight='bold')
fig.text(.02,.12,'Enero a diciembre de 2025. Cuatro plantas.',fontsize=7.5)
fig.text(.02,.065,'Fuente: Minería 3 y API mindicador.cl.',fontsize=7.5)
fig.text(.02,.015,'Descomposición contable; no es utilidad.',fontsize=7.5)
fig.savefig(OUT/'figura_3.png');plt.close(fig)

z=F[F.mes.isin(['2025-01','2025-12'])].pivot(index='nombre',columns='mes',values='c_ops');z=z.loc[['Planta Cerro Norte','Planta Loa','Planta Salado','Planta Illapel']]
fig,ax=plt.subplots(figsize=(3.1,2.6));fig.subplots_adjust(left=.30,right=.91,top=.69,bottom=.28)
fig.text(.02,.96,'Figura 4  Costo por planta · USD/lb',ha='left',va='top',weight='bold',fontsize=9)
y=np.arange(4)
ax.barh(y-.16,z['2025-01'],height=.27,color=light,label='Enero');ax.barh(y+.16,z['2025-12'],height=.27,color=blue,label='Diciembre')
ax.set_yticks(y,[s.replace('Planta ','') for s in z.index],fontsize=8.5);ax.invert_yaxis();ax.set_xlim(0,4.55);ax.set_xticks([0,2,4]);ax.xaxis.set_major_formatter(comma);ax.grid(axis='x');ax.set_axisbelow(True)
ax.legend(loc='upper left',bbox_to_anchor=(-.38,1.43),ncol=2,frameon=False,fontsize=8)
for i,v in enumerate(z['2025-12']):ax.text(v+.07,i+.16,fmt(v,2),va='center',fontsize=8)
fig.text(.02,.12,'2025. Ley de Operaciones y datos válidos.',fontsize=7.5)
fig.text(.02,.065,'Fuente: Minería 3 y dólar de mindicador.cl.',fontsize=7.5)
fig.text(.02,.015,'Elaboración propia.',fontsize=7.5)
fig.savefig(OUT/'figura_4.png');plt.close(fig)
from PIL import Image
left=Image.open(OUT/'figura_3.png').convert('RGB');right=Image.open(OUT/'figura_4.png').convert('RGB')
combined=Image.new('RGB',(left.width+right.width,max(left.height,right.height)),'white');combined.paste(left,(0,0));combined.paste(right,(left.width,0));combined.save(OUT/'figuras_3_4.png')
assert abs(sum(values[:4])-values[4])<1e-10
print('Tres figuras generadas y puente reconciliado.')
