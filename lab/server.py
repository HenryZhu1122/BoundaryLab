from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .engine import ROOT, RUNS, find_ngspice, simulate
from .export import export_study
from .models import Circuit, Contract, ExperimentRequest, InvestigationRequest
from .research import STUDIES, Study

load_dotenv(ROOT/'.env')
app=FastAPI(title='芯界 BoundaryLab',version=__version__)
studies={}
start_lock=threading.Lock()


@app.get('/api/health')
def health():
    load_dotenv(ROOT/'.env',override=True)
    try:
        engine=bool(find_ngspice())
    except RuntimeError: engine=False
    return {'version':__version__,'simulator_ready':engine,
            'api_configured':bool(os.getenv('DEEPSEEK_API_KEY')),
            'model':os.getenv('DEEPSEEK_MODEL','deepseek-flash'),
            'model_disclosure':'通用行为模型；不是商业器件或工艺模型。'}


@app.get('/api/presets')
def presets():
    return [
        {'id':'amplifier','name':'精密放大器','subtitle':'增益看似正确，工作条件会改变结论。',
         'circuit':Circuit().model_dump(),'contract':Contract().model_dump()},
        {'id':'lowpass','name':'有源低通滤波器','subtitle':'区分预期频响与非理想器件带来的额外失效。',
         'circuit':Circuit(kind='lowpass',gain=10,cutoff_hz=20000).model_dump(),
         'contract':Contract(frequency_max_hz=200000,amplitude_max_v=.8).model_dump()},
    ]


@app.post('/api/experiments')
def experiment(request:ExperimentRequest):
    try: return simulate(request.circuit,request.experiment,request.contract)
    except RuntimeError as exc: raise HTTPException(422,str(exc)) from None


@app.post('/api/studies')
def create(request:InvestigationRequest):
    with start_lock:
        if any(s.status=='running' for s in studies.values()):
            raise HTTPException(409,'已有研究正在运行，请等待完成或停止当前研究。')
        study=Study(request);studies[study.id]=study
        threading.Thread(target=study.run,daemon=True).start()
        return {'id':study.id}


@app.get('/api/studies')
def list_studies():
    rows=[]
    if STUDIES.exists():
        for folder in sorted(STUDIES.iterdir(),reverse=True):
            p=folder/'study.json'
            if p.exists():
                try:
                    s=studies[folder.name].snapshot() if folder.name in studies else json.loads(p.read_text(encoding='utf-8'))
                    if s['request'].get('purpose')=='benchmark': continue
                    rows.append({k:s[k] for k in ['id','status','created_at']})
                except (ValueError,KeyError): pass
    return rows[:30]


def fetch(study_id):
    if not re.fullmatch(r'[\w-]{1,80}',study_id): raise HTTPException(404)
    if study_id in studies: return studies[study_id].snapshot()
    p=STUDIES/study_id/'study.json'
    if not p.exists(): raise HTTPException(404,'研究记录不存在')
    s=json.loads(p.read_text(encoding='utf-8'))
    if s['status']=='running' and time.time()-p.stat().st_mtime>120:
        s['status']='interrupted';s['phase']='服务重启后已中断，可读取原有证据'
    return s


@app.get('/api/featured')
def featured():
    p=ROOT/'artifacts'/'featured.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


@app.get('/api/studies/{study_id}')
def detail(study_id:str): return fetch(study_id)


@app.post('/api/studies/{study_id}/cancel')
def cancel(study_id:str):
    if study_id not in studies: raise HTTPException(404)
    studies[study_id].cancelled=True
    return {'status':'stopping'}


@app.get('/api/studies/{study_id}/export')
def export(study_id:str):
    snapshot=fetch(study_id)
    if snapshot['status']=='running': raise HTTPException(409,'请等待研究完成或停止后导出')
    if study_id in studies: study=studies[study_id]
    else:
        # Export a persisted study without invoking its constructor or rerunning it.
        study=object.__new__(Study)
        study.id=study_id;study.folder=STUDIES/study_id
        study.save=lambda:None;study.snapshot=lambda:snapshot
    p=export_study(study)
    return FileResponse(p,filename=f'BoundaryLab-{study_id}.zip')


@app.get('/api/measurements/{run_id}')
def measurement(run_id:str):
    if not re.fullmatch(r'[a-f0-9]{16}',run_id): raise HTTPException(404)
    p=RUNS/run_id/'measurement.json'
    if not p.exists(): raise HTTPException(404)
    return json.loads(p.read_text(encoding='utf-8'))


@app.get('/api/measurements/{run_id}/netlist')
def source(run_id:str):
    if not re.fullmatch(r'[a-f0-9]{16}',run_id): raise HTTPException(404)
    p=RUNS/run_id/'circuit.cir'
    if not p.exists(): raise HTTPException(404)
    return {'text':p.read_text(encoding='ascii')}


app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='web')
