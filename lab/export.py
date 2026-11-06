from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from .engine import RUNS


def referenced_ids(snapshot):
    ids={m['id'] for m in snapshot.get('measurements',[])}
    if snapshot.get('map'):
        ids.update(p['id'] for p in snapshot['map']['points'])
    repair=snapshot.get('repair')
    if repair:
        ids.update(p['after']['id'] for p in repair['checks'])
        if repair.get('after_map'): ids.update(p['id'] for p in repair['after_map']['points'])
        for iteration in repair.get('iterations',[]):
            if iteration.get('validation_map'):
                ids.update(p['id'] for p in iteration['validation_map']['points'])
    for event in snapshot.get('events',[]):
        ids.update(event.get('evidence_ids',[]))
    return ids


def markdown_report(s):
    r=s.get('report') or {}
    lines=[f"# 芯界实验报告 / {s['id']}","",f"- 创建时间（UTC）：{s['created_at']}",
           f"- 状态：{s['status']}",f"- 策略：{s['request']['mode']}",
           f"- 研究问题：{s['request']['question']}","","## 验收合同","",
           '```json',json.dumps(s['request']['contract'],ensure_ascii=False,indent=2),'```',
           "","## 搜索实验","","| 运行 ID | 频率 Hz | 输入峰值 V | 增益误差 | 残差失真 | 通过 |",
           "|---|---:|---:|---:|---:|---|"]
    for p in s.get('measurements',[]):
        e=p['experiment']
        lines.append(f"| {p['id']} | {e['frequency_hz']:.4g} | {e['amplitude_v']:.4g} | {p['gain_error']:.3%} | {p['distortion']:.3%} | {'是' if p['passed'] else '否'} |")
    lines += ['','## 机制证据','']
    for m in r.get('mechanisms',[]):
        lines += [f"### {m['title']}：{m['status']}",m['description'],
                  '证据：'+(', '.join(m['evidence_ids']) or '暂无'),m['limitation'],'']
    if s.get('map'):
        m=s['map'];lines+=['## 独立工作域测量','',f"通过 {m['pass_count']}/{m['measured_count']} 个固定网格点。",m['interpretation'],'']
    if s.get('repair'):
        p=s['repair'];lines+=['## 候选修改','',p['summary'],p['tradeoff'],p['selection_method'],'','```diff',p['netlist_diff'],'```','']
        if p.get('after_map'):
            a=p['after_map'];lines += [f"候选独立网格通过 {a['pass_count']}/{a['measured_count']} 点。",'']
        if p.get('iterations'):
            lines+=['候选修改轨迹：','']
            for i,it in enumerate(p['iterations'],1):
                lines.append(f"- 第 {i} 轮：GBW {it['device']['gbw_hz']:.6g} Hz，SR {it['device']['slew_v_us']:.6g} V/µs，网格通过 {it['pass_count']} 点。")
            lines.append('')
    lines+=['## 结论边界','','本作品使用公开透明的通用行为运放模型，未进行真实器件实验或工艺签核。',
            '工作域图展示离散采样；没有测量的连续区域不构成已验证区域。',
            '失真指标为移除 DC 与基波后的残差 RMS / 基波 RMS，包含数值误差。',
            'journal.jsonl 的哈希链提供内部一致性检查，不提供外部时间戳或不可篡改保证。','',
            '## 重跑','','在作品根目录运行：',f'`python -m lab.cli replay evidence/{s["id"]}/study.json`','']
    return '\n'.join(lines)


def export_study(study):
    study.save(); s=study.snapshot()
    report=markdown_report(s)
    (study.folder/'report.md').write_text(report,encoding='utf-8')
    output=study.folder/'evidence.zip'
    files=[]
    for name in ['study.json','journal.jsonl','report.md','model_transcript.json']:
        p=study.folder/name
        if p.exists(): files.append((p,f'evidence/{study.id}/{name}'))
    for rid in sorted(referenced_ids(s)):
        for name in ['config.json','circuit.cir','samples.tsv','simulator.log','measurement.json']:
            p=RUNS/rid/name
            if p.exists(): files.append((p,f'evidence/{study.id}/runs/{rid}/{name}'))
    manifest={arc:hashlib.sha256(p.read_bytes()).hexdigest() for p,arc in files}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,arc in files: z.write(p,arc)
        z.writestr('manifest.sha256.json',json.dumps(manifest,indent=2))
    return output
