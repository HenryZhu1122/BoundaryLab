"""Frozen small benchmark, equal search budgets, transparent baselines.

The model sees the declared circuit parameters (white-box study); this is not
a hidden-circuit benchmark. All measurements use the same simulator/validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import time
from pathlib import Path

import numpy as np

from lab.engine import ROOT, brief, simulate
from lab.models import Circuit, Contract, Device, Experiment, InvestigationRequest
from lab.research import Study, build_report, local_next


def tasks():
    return [
        ('bandwidth',Circuit(device=Device(gbw_hz=300000,slew_v_us=20,swing_v=8)),Contract(frequency_min_hz=500,frequency_max_hz=150000,amplitude_min_v=.002,amplitude_max_v=.02)),
        ('slew',Circuit(device=Device(gbw_hz=40000000,slew_v_us=.1,swing_v=12)),Contract(frequency_min_hz=2000,frequency_max_hz=20000,amplitude_min_v=.02,amplitude_max_v=.15)),
        ('saturation',Circuit(device=Device(gbw_hz=20000000,slew_v_us=20,swing_v=2)),Contract(frequency_min_hz=100,frequency_max_hz=3000,amplitude_min_v=.05,amplitude_max_v=.7)),
        ('combined',Circuit(),Contract()),
        ('normal_amplifier',Circuit(device=Device(gbw_hz=8000000,slew_v_us=8)),Contract(frequency_min_hz=100,frequency_max_hz=3000,amplitude_min_v=.002,amplitude_max_v=.05)),
        ('lowpass',Circuit(kind='lowpass',gain=10,cutoff_hz=20000),Contract(frequency_min_hz=500,frequency_max_hz=200000,amplitude_min_v=.005,amplitude_max_v=.8)),
        ('normal_lowpass',Circuit(kind='lowpass',gain=2,cutoff_hz=2000,device=Device(gbw_hz=20000000,slew_v_us=20)),Contract(frequency_min_hz=100,frequency_max_hz=10000,amplitude_min_v=.002,amplitude_max_v=.1)),
        ('high_gain',Circuit(gain=40,device=Device(gbw_hz=1500000,slew_v_us=.5)),Contract(frequency_min_hz=300,frequency_max_hz=100000,amplitude_min_v=.002,amplitude_max_v=.15)),
    ]


def scripted(method,request,seed):
    con=request.contract;rng=random.Random(seed);rows=[]
    fixed=[(0,0),(1,0),(0,1),(1,1),(.5,.5),(.25,.75),(.75,.25),(.5,0),(0,.5),(1,.5)]
    for i in range(request.budget):
        if i==0:
            e=Experiment(frequency_hz=float(np.clip(1000,con.frequency_min_hz,con.frequency_max_hz)),
                         amplitude_v=float(np.clip(.02,con.amplitude_min_v,con.amplitude_max_v)))
        elif method=='local':e,_=local_next(rows,request)
        else:
            x,y=fixed[i%len(fixed)] if method=='fixed' else (rng.random(),rng.random())
            e=Experiment(frequency_hz=con.frequency_min_hz*(con.frequency_max_hz/con.frequency_min_hz)**x,
                         amplitude_v=con.amplitude_min_v*(con.amplitude_max_v/con.amplitude_min_v)**y)
        rows.append(brief(simulate(request.circuit,e,con)))
    return rows,build_report(rows,request)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--include-model',action='store_true');args=parser.parse_args()
    out=ROOT/'artifacts'/'benchmark';out.mkdir(parents=True,exist_ok=True)
    taskdata=[{'id':name,'circuit':c.model_dump(),'contract':con.model_dump()} for name,c,con in tasks()]
    # Freeze before the first evaluation. The hash is included in all outputs.
    contract={'version':'boundarylab-small-v1','budget':8,'random_seeds':[17,42,93],
              'model_repeats':1,'tasks':taskdata,'limitations':['8 synthetic tasks only','single model run per task',
              'circuit parameters visible to the model','normal cases not a continuous-domain proof'],
              'metrics':['failure_found_within_budget','first_failure_index','observations_supporting_mechanisms','wall_time_s','tokens']}
    content=json.dumps(contract,ensure_ascii=False,sort_keys=True,indent=2)
    (out/'experiment_contract.json').write_text(content,encoding='utf-8')
    digest=hashlib.sha256(content.encode()).hexdigest()
    results=[]
    for name,circuit,con in tasks():
        for method in ['fixed','random','local']+(['deepseek'] if args.include_model else []):
            for seed in ([17,42,93] if method=='random' else [42]):
                request=InvestigationRequest(purpose='benchmark',circuit=circuit,contract=con,budget=8,
                    mode='deepseek' if method=='deepseek' else 'local',build_map=False,auto_repair=False,
                    question='在冻结输入域和8次仿真预算内查找反例，并使用对照实验区分可能的失效机制。不要修改验收条件。')
                started=time.perf_counter();usage=None;studyid=None
                if method=='deepseek':
                    study=Study(request);study.run();studyid=study.id
                    rows=study.measurements;report=study.report or build_report(rows,request)
                    usage=study.provider_usage
                    status=study.status
                else:rows,report=scripted(method,request,seed);status='completed'
                result={'task':name,'method':method,'seed':seed,'status':status,'study_id':studyid,
                        'first_failure_index':next((i+1 for i,r in enumerate(rows) if not r['passed']),None),
                        'failure_found_within_budget':any(not r['passed'] for r in rows),
                        'failures':sum(not r['passed'] for r in rows),'simulations':len(rows),
                        'supported_mechanisms':[m['key'] for m in report['mechanisms'] if m['status']!='证据不足'],
                        'controlled_mechanisms':[m['key'] for m in report['mechanisms'] if m['status']=='对照支持'],
                        'wall_time_s':round(time.perf_counter()-started,3),'usage':usage,'measurements':rows}
                results.append(result)
                (out/'results.json').write_text(json.dumps({'contract_sha256':digest,'python':platform.python_version(),
                    'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
                print(f'{name:18} {method:10} seed={seed} first={result["first_failure_index"]} mechanisms={result["supported_mechanisms"]}',flush=True)
    lines=['# 小规模冻结评测','',f'实验合同 SHA-256：`{digest}`','',
           '每任务搜索预算8次，均包含同一个标称基线；独立工作域地图与设计修改不参与该评测。',
           '模型每任务1次，随机搜索3个种子；本结果不支持显著性或广泛泛化声明。','',
           '| 任务 | 方法 | 种子 | 首反例次数 | 支持的机制 | 耗时 s |',
           '|---|---|---:|---:|---|---:|']
    for r in results:
        first=r['first_failure_index'] if r['first_failure_index'] is not None else f'未发现（{r["simulations"]}/8）'
        lines.append(f'| {r["task"]} | {r["method"]} | {r["seed"]} | {first} | {", ".join(r["supported_mechanisms"])} | {r["wall_time_s"]} |')
    lines+=['','未发现反例的任务保留在表中，不从成功案例均值中消失。已发现反例由共同冻结验证器确认。',
            '机制数量来自保守规则审查，属于覆盖指标，不等于独立人工验证的诊断准确率。',
            '带宽和SR等效应可共存；正常案例上的边界外失效不能算作域内反例。',
            '缓存会显著改变壁钟时间，因此耗时仅供本机运行参考，不作为算法优劣证据。']
    (out/'评测报告.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
