from __future__ import annotations

import difflib
import hashlib
import json
import math
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .engine import ROOT, RUNS, brief, netlist, simulate
from .models import Circuit, Device, Experiment, InvestigationRequest
from .provider import DeepSeek, TOOLS, DESIGN_TOOL, system_prompt

STUDIES = ROOT / "artifacts" / "studies"


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Study:
    def __init__(self, request: InvestigationRequest):
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.folder = STUDIES / self.id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.request = request
        self.events = []
        self.measurements = []
        self.status = "running"
        self.phase = "准备实验"
        self.report = None
        self.map = None
        self.repair = None
        self.provider_usage = None
        self.design_proposal = None
        self.created_at = stamp()
        self.cancelled = False
        self.lock = threading.RLock()
        self.previous_hash = "0"*64

    def event(self, kind: str, title: str, body: str = "", **data):
        with self.lock:
            item = {"seq":len(self.events)+1,"time":stamp(),"kind":kind,"title":title,"body":body,**data}
            item['previous_hash'] = self.previous_hash
            digest = hashlib.sha256(json.dumps(item,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            item['hash'] = digest
            self.previous_hash = digest
            self.events.append(item)
            with (self.folder / "journal.jsonl").open('a',encoding='utf-8') as f:
                f.write(json.dumps(item,ensure_ascii=False)+"\n")
            self.save()

    def snapshot(self):
        with self.lock:
            return {"id":self.id,"created_at":self.created_at,"status":self.status,"phase":self.phase,
                    "request":self.request.model_dump(),"events":self.events.copy(),
                    "measurements":self.measurements.copy(),"map":self.map,"repair":self.repair,
                    "report":self.report,"provider_usage":self.provider_usage}

    def save(self):
        with self.lock:
            path = self.folder / "study.json"
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.snapshot(),ensure_ascii=False,indent=2),encoding='utf-8')
            # Windows readers/antivirus may briefly open the destination without
            # FILE_SHARE_DELETE. Preserve atomic replacement and retry briefly.
            for attempt in range(7):
                try:
                    tmp.replace(path)
                    break
                except PermissionError:
                    if attempt==6: raise
                    time.sleep(min(.02*2**attempt,.2))

    def execute(self, exp: Experiment, plan: dict, source: str):
        self.event("plan","实验计划已登记",plan.get('rationale',exp.purpose),
                   plan={**plan,"frequency_hz":exp.frequency_hz,"amplitude_v":exp.amplitude_v},source=source)
        result = simulate(self.request.circuit,exp,self.request.contract)
        small = brief(result)
        self.measurements.append(small)
        self.event("measurement","通过验收" if result['passed'] else "发现失效",
                   f"增益误差 {result['gain_error']*100:.2f}%，残差失真 {result['distortion']*100:.2f}%",
                   measurement=small,source="ngspice",
                   prediction_match=(plan['expected_pass']==result['passed']) if isinstance(plan.get('expected_pass'),bool) else None)
        return small

    def run(self):
        provider = None
        try:
            self.event("start","研究启动",self.request.question,source=self.request.mode)
            self.phase = "标称条件检验"
            c=self.request.contract
            f=float(np.clip(1000,c.frequency_min_hz,c.frequency_max_hz))
            a=float(np.clip(.02,c.amplitude_min_v,c.amplitude_max_v))
            first = self.execute(Experiment(frequency_hz=f,amplitude_v=a,purpose="标称基线"),
                {"hypothesis":"标称可用性","prediction":"先确认小信号基线；若失败，将据此调整调查方向。",
                 "rationale":"建立后续对照的参考，结果由仿真判定。"},"baseline")
            if self.request.mode == "deepseek":
                provider = DeepSeek()
                self.model_loop(provider,first)
                self.provider_usage = {"model":provider.model,"calls":provider.calls,**provider.usage}
            else:
                self.local_loop()
            if self.cancelled:
                self.status="cancelled"; self.phase="已停止"; self.save(); return
            self.phase="证据审查"
            self.report = build_report(self.measurements,self.request,self.events)
            self.event("review","实验记录审查完成",f"形成 {len(self.report['mechanisms'])} 项机制审查记录。",
                       source="deterministic-review")
            if self.request.build_map:
                self.phase="独立工作域测量"
                self.event("map_start","测量工作域","每个地图点均单独调用 ngspice；这是独立验证预算，不计入 Agent 搜索预算。")
                self.map=build_map(self.request.circuit,self.request.contract,cancel=lambda:self.cancelled)
                self.save()
                if self.cancelled:
                    self.status='cancelled';self.phase='已停止';self.save();return
            if self.request.auto_repair:
                self.phase="候选修改与独立复测"
                if provider and not self.cancelled:
                    self.design_proposal=propose_candidate(provider,self.request,self.measurements)
                    self.event('design_proposal','Agent 提交设计候选',self.design_proposal['rationale'],
                               proposal=self.design_proposal,source='deepseek')
                self.repair=repair_design(self.request,self.measurements,self.map,self.design_proposal,cancel=lambda:self.cancelled)
                self.event("repair","候选修改已复测",self.repair['summary'],source="verified-design-candidate")
                iterations=[{'device':self.repair['after_device'],'proposal':self.design_proposal,
                             'pass_count':(self.repair.get('after_map') or {}).get('pass_count'),
                             'validation_map':self.repair.get('after_map')}]
                # Feed independently measured residual failures back to the model.
                # The original acceptance contract stays frozen throughout.
                if provider and self.repair.get('after_map') and not self.cancelled:
                    candidate=Circuit(**self.repair['circuit'])
                    remaining=[p for p in self.repair['after_map']['points'] if not p['passed'] and
                               p['expected_gain']*p['experiment']['amplitude_v']<.9*candidate.device.swing_v]
                    if remaining:
                        self.event('revision','独立复测发现候选仍有遗漏',
                                   f'{len(remaining)} 个未触及理想摆幅约束的网格点仍不通过，将测量返回 Agent。',
                                   evidence_ids=[p['id'] for p in remaining[:8]])
                        follow_request=self.request.model_copy(update={'circuit':candidate})
                        proposal=propose_candidate(provider,follow_request,
                            sorted(remaining,key=lambda p:p['margin'])[:8])
                        self.event('design_proposal','Agent 修订设计候选',proposal['rationale'],proposal=proposal,source='deepseek')
                        self.repair=repair_design(self.request,self.measurements,self.map,proposal,cancel=lambda:self.cancelled)
                        iterations.append({'device':self.repair['after_device'],'proposal':proposal,
                                           'pass_count':(self.repair.get('after_map') or {}).get('pass_count'),
                                           'validation_map':self.repair.get('after_map')})
                        self.event('repair','修订候选已完成复测',self.repair['summary'],source='ngspice')
                if self.repair: self.repair['iterations']=iterations
            self.status="cancelled" if self.cancelled else "completed"
            self.phase="已停止" if self.cancelled else "研究完成"
            self.event("complete","研究完成" if not self.cancelled else "研究已停止",
                       "可导出原始波形、模型计划、网表、日志和可重跑配置。")
        except Exception as exc:
            self.status="failed"; self.phase="运行中断"
            # Exception messages from our execution layer never include secrets.
            self.event("error","运行中断",str(exc)[:400])
        finally:
            if provider:
                self.provider_usage={"model":provider.model,"calls":provider.calls,**provider.usage}
                (self.folder/'model_transcript.json').write_text(json.dumps(provider.transcript,ensure_ascii=False,indent=2),encoding='utf-8')
            self.save()

    def model_loop(self, provider: DeepSeek, first: dict):
        messages=[{"role":"system","content":system_prompt(self.request)},
                  {"role":"user","content":self.request.question+"\n已自动执行标称基线："+json.dumps(first,ensure_ascii=False)}]
        rejected=0
        self.phase="Agent 自主实验"
        for _ in range(self.request.budget+3):
            if self.cancelled or len(self.measurements)>=self.request.budget: break
            message=provider.call(messages,TOOLS)
            messages.append(message)
            calls=message.get('tool_calls',[])
            if not calls:
                if len(self.measurements)>=4:
                    self.event('model_note','模型结束本轮搜索',str(message.get('content',''))[:1800],source='deepseek')
                    break
                messages.append({'role':'user','content':'请继续调用 run_experiment 工具，至少完成四个有区分力的实验。'})
                rejected+=1
                if rejected>=3: raise RuntimeError('模型连续未给出有效工具调用。')
                continue
            finished=False
            for call in calls:
                response={}
                try:
                    function=call['function']; args=json.loads(function['arguments'])
                    if function['name']=='finish_investigation':
                        known={r['id'] for r in self.measurements}
                        if not set(args.get('evidence_ids',[])).issubset(known):
                            raise ValueError('报告引用了不存在的实验 ID')
                        if len(self.measurements)<4: raise ValueError('尚未完成四个实验，请继续区分机制')
                        self.event('model_note','模型研究小结',str(args.get('summary',''))[:1800],
                                   uncertainty=str(args.get('remaining_uncertainty',''))[:1000],source='deepseek')
                        response={'accepted':True};finished=True
                    elif function['name']=='run_experiment':
                        if len(self.measurements)>=self.request.budget:
                            response={'error':'仿真搜索预算已耗尽，请结束。'}
                        else:
                            exp=Experiment(frequency_hz=args['frequency_hz'],amplitude_v=args['amplitude_v'],
                                           purpose=str(args.get('hypothesis','自主实验'))[:300])
                            con=self.request.contract
                            if not (con.frequency_min_hz<=exp.frequency_hz<=con.frequency_max_hz and
                                    con.amplitude_min_v<=exp.amplitude_v<=con.amplitude_max_v):
                                raise ValueError('实验超出合同输入域')
                            if any(abs(math.log(r['experiment']['frequency_hz']/exp.frequency_hz))<1e-5 and
                                   abs(math.log(r['experiment']['amplitude_v']/exp.amplitude_v))<1e-5 for r in self.measurements):
                                raise ValueError('该点已测量，请选择新的实验')
                            if not isinstance(args.get('expected_pass'),bool):
                                raise ValueError('expected_pass 必须是布尔值，请登记事先预测')
                            plan={k:str(args.get(k,''))[:700] for k in ('hypothesis','prediction','rationale')}
                            plan['expected_pass']=args['expected_pass']
                            response=self.execute(exp,plan,'deepseek')
                            rejected=0
                    else: raise ValueError('不支持的工具')
                except (ValueError,KeyError,TypeError) as exc:
                    response={'error':str(exc)[:250]};rejected+=1
                    self.event('tool_rejected','工具请求未通过校验',response['error'],source='validator')
                messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(response,ensure_ascii=False)})
            if finished: break
            if rejected>=4: raise RuntimeError('模型工具调用连续未通过校验，研究已停止。')
            messages.append({'role':'user','content':f'剩余搜索仿真预算 {self.request.budget-len(self.measurements)}；优先区分尚未区分的机制，或细化边界。'})

    def local_loop(self):
        self.phase="本地实验策略（非大模型）"
        while len(self.measurements)<self.request.budget and not self.cancelled:
            exp,plan=local_next(self.measurements,self.request)
            self.execute(exp,plan,'local-policy')


def local_next(measurements,request):
    c=request.contract; dev=request.circuit.device
    used={(round(x['experiment']['frequency_hz'],4),round(x['experiment']['amplitude_v'],6)) for x in measurements}
    # A distorted observation triggers a same-frequency small-signal control.
    candidates=[]
    for r in reversed(measurements):
        if r['distortion']>c.distortion_limit:
            candidates.append((r['experiment']['frequency_hz'],c.amplitude_min_v,'非线性机制对照',
                               '同频减小幅值后，非线性失真应显著降低；若增益误差仍在，保留带宽解释。'))
    candidates += [(c.frequency_max_hz,c.amplitude_min_v,'高频小信号','若增益下降且失真低，则支持带宽相关解释。'),
                   (min(c.frequency_max_hz,dev.gbw_hz/request.circuit.gain*.625),min(c.amplitude_max_v,.2),'大信号动态响应','若斜率接近限制且未触轨，检验压摆率机制。'),
                   (c.frequency_min_hz,c.amplitude_max_v,'低频幅值极限','降低频率保留幅值，检验输出摆幅限制。')]
    small=[r for r in measurements if r['experiment']['amplitude_v']<=max(c.amplitude_min_v*1.1,.006)]
    passes=[r['experiment']['frequency_hz'] for r in small if r['passed']]
    fails=[r['experiment']['frequency_hz'] for r in small if not r['passed']]
    if fails:
        lower=max([c.frequency_min_hz]+[f for f in passes if f<min(fails)])
        upper=min(fails)
        candidates.append((math.sqrt(lower*upper),c.amplitude_min_v,'边界细化','在已知通过与失败之间选择对数中点，缩小边界区间。'))
    for f,a,h,p in candidates:
        f=float(np.clip(f,c.frequency_min_hz,c.frequency_max_hz));a=float(np.clip(a,c.amplitude_min_v,c.amplitude_max_v))
        if (round(f,4),round(a,6)) not in used:
            return Experiment(frequency_hz=f,amplitude_v=a,purpose=h),{'hypothesis':h,'prediction':p,'rationale':'根据当前测量选择尚未执行的对照或边界实验；本地数值策略。'}
    # Finite deterministic design, with nonduplicate points across a full budget.
    i=len(measurements)
    return Experiment(frequency_hz=float(c.frequency_min_hz*(c.frequency_max_hz/c.frequency_min_hz)**((i*.61803398875)%1)),
                      amplitude_v=float(c.amplitude_min_v*(c.amplitude_max_v/c.amplitude_min_v)**((i*.41421356237)%1))),{
        'hypothesis':'补充覆盖','prediction':'该点未测量，不预设通过或失败。','rationale':'避免重复测量，增加工作域覆盖。'}


def build_report(rows,request,events=None):
    con=request.contract
    bw=[r for r in rows if r['gain_error']>con.gain_error_limit and r['distortion']<.01 and r['slew_utilization']<.75 and r['rail_occupancy']<.01]
    sr=[r for r in rows if r['distortion']>con.distortion_limit and r['slew_utilization']>.9 and r['rail_occupancy']<.01]
    rail=[r for r in rows if r['rail_occupancy']>.08 and not r['passed']]
    mechanisms=[]
    for key,title,group,description in [
        ('bandwidth','带宽相关限制',bw,'低失真情况下出现增益下降与相位滞后，与有限带宽一致。'),
        ('slew','压摆率相关限制',sr,'输出斜率接近模型限制并出现非线性失真，且没有明显触轨。'),
        ('saturation','输出摆幅限制',rail,'输出多次接近模型输出轨，存在幅值压缩。')]:
        controlled=[]
        for r in group:
            for other in rows:
                if other['id']==r['id']: continue
                same_f=abs(math.log(other['experiment']['frequency_hz']/r['experiment']['frequency_hz']))<.02
                small=other['experiment']['amplitude_v']<r['experiment']['amplitude_v']*.4
                if same_f and small:
                    if key=='bandwidth' and abs(other['gain_error']-r['gain_error'])<.03:
                        controlled.append(other)
                    elif key in ('slew','saturation') and other['distortion']<r['distortion']*.4:
                        controlled.append(other)
        ids=list(dict.fromkeys(x['id'] for x in group+controlled))
        mechanisms.append({'key':key,'title':title,'status':'对照支持' if group and controlled else ('观测支持' if group else '证据不足'),
                           'description':description if group else '当前实验未得到足够支持，不排除该机制。',
                           'evidence_ids':ids,'limitation':'行为模型内的机制审查，不构成真实芯片唯一因果证明。'})
    checks=[{'run_id':e['measurement']['id'],'matched':e['prediction_match']}
            for e in (events or []) if e.get('prediction_match') is not None]
    return {'simulations':len(rows),'failures':sum(not r['passed'] for r in rows),'mechanisms':mechanisms,
            'prediction_checks':checks,'predictions_refuted':sum(not e['matched'] for e in checks),
            'first_counterexample':next((r['id'] for r in rows if not r['passed']),None),
            'limitations':['有限实验不能证明整个连续工作域正确。','通用行为模型不代表具体商业运放或流片结果。',
                           '残差失真包含数值误差，近阈值点需要步长复核。'],
            'engine':'ngspice-47','review_method':'deterministic-evidence-rules-v1'}


def build_map(circuit,contract,nf=15,na=11,cancel=lambda:False):
    fs=np.geomspace(contract.frequency_min_hz,contract.frequency_max_hz,nf)
    amps=np.geomspace(contract.amplitude_min_v,contract.amplitude_max_v,na)
    points=[Experiment(frequency_hz=float(f),amplitude_v=float(a),purpose='独立工作域验证') for a in amps for f in fs]
    def run(e):
        if cancel(): return None
        return brief(simulate(circuit,e,contract))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=[r for r in pool.map(run,points) if r is not None]
    return {'frequencies_hz':fs.tolist(),'amplitudes_v':amps.tolist(),'points':results,
            'measured_count':len(results),'pass_count':sum(r['passed'] for r in results),
            'pass_fraction':sum(r['passed'] for r in results)/max(1,len(results)),
            'interpretation':'固定对数网格上的通过比例，不是连续工作域面积或良率。',
            'budget_category':'independent_validation','circuit':circuit.model_dump()}


def propose_candidate(provider,request,rows):
    messages=[{'role':'system','content':'你是电路设计研究员。根据真实实验提出一个通用行为模型参数候选，调用 propose_device_candidate。GBW 与 SR 不得低于原模型。保持输出摆幅、目标增益、验收阈值和输入域。考虑在5%增益误差要求下 GBW 至少约为最大频率×噪声增益×3.1；SR应覆盖未饱和的正弦输出斜率。无法通过提高GBW或SR修复的摆幅问题要保留。不要虚构功耗、成本、商业料号或实测。用中文简短说明。'},
              {'role':'user','content':json.dumps({'circuit':request.circuit.model_dump(),'contract':request.contract.model_dump(),'measurements':rows},ensure_ascii=False)}]
    for _ in range(2):
        response=provider.call(messages,DESIGN_TOOL)
        messages.append(response)
        calls=response.get('tool_calls',[])
        if not calls:
            messages.append({'role':'user','content':'请调用提供的设计候选工具。'})
            continue
        call=calls[0]
        try:
            if call['function']['name']!='propose_device_candidate': raise ValueError('工具名称错误')
            proposal=json.loads(call['function']['arguments'])
            dev=request.circuit.device
            Device(gbw_hz=proposal['gbw_hz'],slew_v_us=proposal['slew_v_us'])
            if proposal['gbw_hz']<dev.gbw_hz or proposal['slew_v_us']<dev.slew_v_us:
                raise ValueError('候选参数不可低于原设计')
            for key in ['rationale','expected_tradeoff','unresolved_limits']:
                if not isinstance(proposal.get(key),str): raise ValueError('候选说明缺失')
            return proposal
        except (ValueError,KeyError,TypeError):
            for t in calls: messages.append({'role':'tool','tool_call_id':t['id'],'content':'{"error":"候选参数未通过约束检查，请修正"}'})
    raise RuntimeError('模型未提供有效的设计修改候选；未替换为固定方案。')


def repair_design(request,rows,before_map,proposal=None,cancel=lambda:False):
    old=request.circuit
    # The model proposes parameters; the validator preserves the original spec.
    # Offline mode uses an explicitly labeled fixed candidate.
    dev=old.device.model_copy(update={'name':'BL-02 / 高速候选行为模型',
                                     'gbw_hz':proposal['gbw_hz'] if proposal else min(50_000_000,max(old.device.gbw_hz,8_000_000)),
                                     'slew_v_us':proposal['slew_v_us'] if proposal else max(old.device.slew_v_us,8)})
    new=old.model_copy(update={'device':dev})
    checks=[]
    for r in rows:
        if cancel(): break
        e=Experiment(**r['experiment'],purpose='原实验回归')
        after=brief(simulate(new,e,request.contract))
        checks.append({'before':r,'after':after})
    after_map=build_map(new,request.contract,cancel=cancel) if before_map and not cancel() else None
    example=Experiment(frequency_hz=1000,amplitude_v=.02)
    diff=''.join(difflib.unified_diff(netlist(old,example).splitlines(True),netlist(new,example).splitlines(True),
                                     fromfile='before.cir',tofile='candidate.cir'))
    fixed=sum(not p['before']['passed'] and p['after']['passed'] for p in checks)
    regressed=sum(p['before']['passed'] and not p['after']['passed'] for p in checks)
    return {'before_device':old.device.model_dump(),'after_device':dev.model_dump(),
            'circuit':new.model_dump(),'checks':checks,'after_map':after_map,'netlist_diff':diff,
            'fixed_count':fixed,'regressed_count':regressed,
            'summary':f'高速候选模型修复了 {fixed} 个原失败点，回归退化 {regressed} 个；输出摆幅保持不变。',
            'tradeoff':'所需 GBW / SR 提高，实际器件的功耗、成本和稳定性代价尚未测量。候选行为模型不等同于已选定商业器件。',
            'proposal':proposal,
            'selection_method':'DeepSeek 依据实验提出 GBW / SR 候选，冻结其他规格后由工具复测。' if proposal else '本地模式采用固定高速候选；候选验证由工具执行。'}
