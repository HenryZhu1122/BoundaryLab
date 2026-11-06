"""Allowlist package creation with explicit credential exclusion and checksums."""
from pathlib import Path
import hashlib,json,zipfile

from lab.engine import ROOT,RUNS
from lab.export import referenced_ids

OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
featured=json.loads((ROOT/'artifacts/featured.json').read_text(encoding='utf-8'))['id']
benchmark=json.loads((ROOT/'artifacts/benchmark/results.json').read_text(encoding='utf-8'))
study_ids={featured}|{r['study_id'] for r in benchmark['results'] if r.get('study_id')}
files={}


def add(p,arc=None):
    p=Path(p)
    if p.is_file() and p.name not in {'.env'} and '__pycache__' not in p.parts:
        rel=arc or str(p.relative_to(ROOT)).replace('\\','/')
        files['BoundaryLab/'+rel]=p


for name in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','.env.example','.gitignore',
             'requirements.txt','requirements-dev.txt','requirements-tested.txt','启动芯界.cmd']:
    add(ROOT/name)
for folder in ['lab','web','tests','scripts','docs','vendor/Spice64']:
    for p in (ROOT/folder).rglob('*'):add(p)
add(ROOT/'artifacts/featured.json')
for p in (ROOT/'artifacts/benchmark').rglob('*'):add(p)
run_ids=set()
for sid in study_ids:
    folder=ROOT/'artifacts/studies'/sid
    for name in ['study.json','journal.jsonl','model_transcript.json','report.md']:
        add(folder/name)
    snapshot=json.loads((folder/'study.json').read_text(encoding='utf-8'))
    run_ids.update(referenced_ids(snapshot))
for r in benchmark['results']:run_ids.update(p['id'] for p in r['measurements'])
figs=json.loads((ROOT/'docs/figures/source_runs.json').read_text(encoding='utf-8'))
run_ids.update([figs['waveform_comparison']['before'],figs['waveform_comparison']['after']])
for rid in run_ids:
    for name in ['measurement.json','config.json','circuit.cir','samples.tsv','simulator.log']:
        add(RUNS/rid/name)

# Only use the local secret to reject accidental inclusion, never emit it.
secret=None
for line in ((ROOT/'.env').read_text(encoding='utf-8').splitlines() if (ROOT/'.env').exists() else []):
    if line.startswith('DEEPSEEK_API_KEY='):secret=line.partition('=')[2].strip()
manifest={}
for arc,p in files.items():
    content=p.read_bytes()
    if secret and secret.encode() in content:raise RuntimeError('Credential detected in candidate package; packaging aborted.')
    manifest[arc]={'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)}

dest=OUT/'赛道一+芯界BoundaryLab+芯界BoundaryLab.zip'
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for arc,p in sorted(files.items()):z.write(p,arc)
    z.writestr('manifest.sha256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    z.writestr('请先阅读.txt','芯界BoundaryLab参赛作品\n\n请先阅读 BoundaryLab/docs/提交说明.md 和 BoundaryLab/README.md。\nWindows双击 BoundaryLab/启动芯界.cmd。\n公开包不含API密钥，可先审阅历史证据或使用本地策略。\n')
with zipfile.ZipFile(dest) as z:
    assert z.testzip() is None
    assert not any(Path(n).name=='.env' for n in z.namelist())
summary={'file':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
         'files':len(files),'referenced_runs':len(run_ids),'credential_scan':'passed','zip_crc':'passed'}
(OUT/'交付清单.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
