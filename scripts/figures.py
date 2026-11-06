from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

from lab.engine import ROOT,simulate
from lab.models import Circuit,Contract,Experiment

OUT=ROOT/'docs'/'figures';OUT.mkdir(parents=True,exist_ok=True)
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.unicode_minus':False,'axes.labelcolor':'#263742',
                     'text.color':'#18313c','axes.edgecolor':'#b4c3c9','xtick.color':'#526b77',
                     'ytick.color':'#526b77','savefig.facecolor':'white'})
featured=json.loads((ROOT/'artifacts'/'featured.json').read_text())['id']
study=json.loads((ROOT/'artifacts'/'studies'/featured/'study.json').read_text(encoding='utf-8'))


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=220)
    fig.savefig(OUT/(name+'.svg'))
    plt.close(fig)


fig,axs=plt.subplots(1,2,figsize=(9,3.4),layout='constrained',sharex=True,sharey=True)
for ax,mp,title in zip(axs,[study['map'],study['repair']['after_map']],['原始设计','修订候选']):
    for passed,label,color in [(True,'通过','#22846b'),(False,'失效','#ca8648')]:
        pts=[p for p in mp['points'] if p['passed']==passed]
        ax.scatter([p['experiment']['frequency_hz'] for p in pts],
                   [p['experiment']['amplitude_v']*1000 for p in pts],s=18,color=color,label=label,alpha=.9)
    ax.set(xscale='log',yscale='log',xlabel='频率 / Hz',title=f'{title}  {mp["pass_count"]}/{mp["measured_count"]} 点通过')
    ax.grid(alpha=.18);ax.set_axisbelow(True)
axs[0].set_ylabel('输入正弦峰值 / mV')
handles,labels=axs[1].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncols=2,frameon=False,fontsize=9)
save(fig,'工作域对比')

c=Circuit(**study['request']['circuit']);after=Circuit(**study['repair']['circuit']);con=Contract(**study['request']['contract'])
e=Experiment(frequency_hz=50000,amplitude_v=.2,purpose='说明材料补充对照')
before=simulate(c,e,con);better=simulate(after,e,con)
fig,axs=plt.subplots(1,2,figsize=(9,3.2),layout='constrained',sharey=True)
for ax,r,title in zip(axs,[before,better],['原始设计','修订候选']):
    w=r['waveform'];ax.plot(w['time_us'],w['ideal_v'],color='#8596a0',ls='--',lw=1,label='理想参考')
    ax.plot(w['time_us'],w['output_v'],color='#22846b',lw=1.8,label='ngspice 输出')
    ax.set(xlabel='时间 / µs',title=f'{title}  增益误差 {r["gain_error"]:.2%}')
    ax.grid(alpha=.18)
axs[0].set_ylabel('输出电压 / V');axs[1].legend(loc='upper right',fontsize=8)
save(fig,'波形修复对比')

b=json.loads((ROOT/'artifacts'/'benchmark'/'results.json').read_text(encoding='utf-8'))
methods=['fixed','random','local','deepseek'];labels=['固定测试','随机搜索\n3个种子','本地策略','DeepSeek']
fractions=[];counts=[]
for m in methods:
    rr=[r for r in b['results'] if r['method']==m and not r['task'].startswith('normal')]
    ok=sum(r['failure_found_within_budget'] for r in rr);counts.append((ok,len(rr)));fractions.append(ok/len(rr))
fig,ax=plt.subplots(figsize=(7.5,2.8),layout='constrained')
bars=ax.barh(labels[::-1],fractions[::-1],color=['#22846b','#6b909f','#b9c6ca','#6b909f'],height=.55)
for bar,(ok,n) in zip(bars,counts[::-1]):
    ax.text(min(bar.get_width()+.025,1.035),bar.get_y()+bar.get_height()/2,f'{ok}/{n}',va='center',fontsize=10)
ax.set(xlim=(0,1.18),xlabel='预算内找到反例的任务运行比例',xticks=[0,.25,.5,.75,1],xticklabels=['0%','25%','50%','75%','100%'])
ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
save(fig,'冻结评测')

(OUT/'source_runs.json').write_text(json.dumps({'featured_study':featured,'waveform_comparison':{
    'before':before['id'],'after':better['id'],'frequency_hz':50000,'amplitude_v':.2},
    'note':'补充波形对照为真实 ngspice 运行，不计入 Agent 搜索预算或搜索评测。'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Figures created:',OUT)
