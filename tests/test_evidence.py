import hashlib
import json
import zipfile

from lab.engine import brief,simulate
from lab.export import export_study
from lab.models import Circuit,Experiment,InvestigationRequest
from lab.research import Study,build_report,local_next


def test_near_rail_but_passing_sine_is_not_classified_as_saturation():
    request=InvestigationRequest(mode='local',build_map=False,auto_repair=False)
    row=brief(simulate(Circuit(),Experiment(frequency_hz=500,amplitude_v=.4)))
    assert row['passed']
    assert build_report([row],request)['mechanisms'][2]['status']=='证据不足'


def test_adaptive_policy_chooses_control_after_nonlinear_result():
    request=InvestigationRequest(mode='local')
    failure=brief(simulate(Circuit(),Experiment(frequency_hz=50000,amplitude_v=.2)))
    e,_=local_next([failure],request)
    assert e.frequency_hz==50000
    assert e.amplitude_v==request.contract.amplitude_min_v


def test_export_manifest_and_journal_are_consistent():
    s=Study(InvestigationRequest(purpose='benchmark',mode='local',budget=4,build_map=False,auto_repair=False))
    s.run()
    assert s.status=='completed'
    p=export_study(s)
    with zipfile.ZipFile(p) as z:
        manifest=json.loads(z.read('manifest.sha256.json'))
        for name,digest in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
        assert not any(name.endswith('.env') for name in z.namelist())
    previous='0'*64
    for line in (s.folder/'journal.jsonl').read_text(encoding='utf-8').splitlines():
        record=json.loads(line);digest=record.pop('hash')
        assert record['previous_hash']==previous
        assert hashlib.sha256(json.dumps(record,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==digest
        previous=digest


def test_snapshot_save_retries_transient_windows_share_violation(monkeypatch):
    from pathlib import Path
    s=Study(InvestigationRequest(purpose='benchmark',mode='local'))
    original=Path.replace
    attempts=[]
    def flaky(path,target):
        if path.name=='study.tmp' and len(attempts)<2:
            attempts.append(True)
            raise PermissionError('simulated Windows sharing violation')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',flaky)
    s.event('test','原子保存检查')
    assert len(attempts)==2
    saved=json.loads((s.folder/'study.json').read_text(encoding='utf-8'))
    assert saved['events'][0]['title']=='原子保存检查'
