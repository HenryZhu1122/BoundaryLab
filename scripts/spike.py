from lab.models import Circuit, Experiment
from lab.engine import brief, simulate
import json

for f, a in [(1000,.02),(200000,.005),(50000,.2),(500,.8)]:
    print(json.dumps(brief(simulate(Circuit(), Experiment(frequency_hz=f,amplitude_v=a))), ensure_ascii=False))
