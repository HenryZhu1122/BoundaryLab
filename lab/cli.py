from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .engine import RUNS, brief, simulate
from .models import Circuit, Contract, Experiment, InvestigationRequest
from .research import Study


def main():
    parser=argparse.ArgumentParser(description='BoundaryLab circuit research CLI')
    sub=parser.add_subparsers(dest='cmd',required=True)
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8765)
    run=sub.add_parser('run');run.add_argument('--mode',choices=['deepseek','local'],default='local')
    run.add_argument('--budget',type=int,default=8);run.add_argument('--no-map',action='store_true')
    replay=sub.add_parser('replay');replay.add_argument('study_json');replay.add_argument('--all',action='store_true')
    args=parser.parse_args()
    if args.cmd=='serve':
        import uvicorn
        uvicorn.run('lab.server:app',host='127.0.0.1',port=args.port,log_level='warning')
    elif args.cmd=='run':
        s=Study(InvestigationRequest(mode=args.mode,budget=args.budget,build_map=not args.no_map))
        s.run()
        print(json.dumps({'id':s.id,'status':s.status,'report':s.report,'usage':s.provider_usage},ensure_ascii=False,indent=2))
        if s.status=='failed':
            print(s.events[-1]['body']);raise SystemExit(1)
    elif args.cmd=='replay':
        snapshot=json.loads(Path(args.study_json).read_text(encoding='utf-8'))
        c=Circuit(**snapshot['request']['circuit']);con=Contract(**snapshot['request']['contract'])
        deltas=[]
        pairs=[(c,Experiment(**row['experiment']),row,1) for row in snapshot['measurements']]
        if args.all:
            from .export import referenced_ids
            pairs=[]
            for rid in sorted(referenced_ids(snapshot)):
                folder=Path(args.study_json).parent/'runs'/rid
                if not folder.exists():folder=RUNS/rid
                config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
                old=json.loads((folder/'measurement.json').read_text(encoding='utf-8'))
                pairs.append((Circuit(**config['circuit']),Experiment(**config['experiment']),old,config['refinement']))
        for ci,exp,row,refinement in pairs:
            r=simulate(ci,exp,con,use_cache=False,refinement=refinement)
            deltas.append({'id':r['id'],'gain_delta':abs(r['measured_gain']-row['measured_gain']),
                           'distortion_delta':abs(r['distortion']-row['distortion'])})
        print(json.dumps(deltas,indent=2))


if __name__=='__main__': main()
