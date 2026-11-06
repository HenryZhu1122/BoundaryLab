from pathlib import Path
import asyncio, json, subprocess, sys, wave
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'tmp/pydeps'))
import edge_tts, imageio_ffmpeg
OUT=ROOT/'artifacts/publicity';OUT.mkdir(parents=True,exist_ok=True)
SCENES=[
 ('opening','一个电路在某个条件下正常工作，换个频率或输入幅值，还能保持性能吗？'),
 ('intro','这就是芯界 Boundary Lab，一款面向电路学习与科研探索的自主实验智能体。'),
 ('experiment','设定研究对象和性能要求后，芯界能够自主提出假设、规划实验，并调用电路仿真工具，探索电路的失效边界。'),
 ('map','在工作域地图上，可以直观看到达标与失效的测量点。点击测量点，就能查看对应波形和实验数据。'),
 ('prediction','每次实验前，智能体都会记录预测，再根据测量结果修正判断，并对优化方案进行独立复测。'),
 ('comparison','在放大器案例中，经过两轮参数优化，相同验收标准下，一百六十五个采样点中的达标点从八十九个提升至一百三十五个。实验过程均可追溯、可重跑。'),
 ('closing','从假设到实验，从证据到修正。芯界，让每一个结论都有实验依据。'),
]
async def main():
 ff=imageio_ffmpeg.get_ffmpeg_exe();sr=24000
 async def speech(i,t):
  p=OUT/f'voice-{i:02}.mp3'
  # TTS-only homophone prevents the polyphonic character from becoming zhong.
  if not p.exists():await edge_tts.Communicate(t.replace('重跑','崇跑'),'zh-CN-YunxiNeural',rate='+18%').save(str(p))
  return p
 paths=await asyncio.gather(*(speech(i,t) for i,(_,t) in enumerate(SCENES)))
 audio=[np.zeros(int(.35*sr),dtype=np.float32)];cursor=.35;timeline=[];srt=[]
 def stamp(t):
  ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
 for (action,t),path in zip(SCENES,paths):
  raw=subprocess.check_output([ff,'-v','error','-i',str(path),'-f','f32le','-ac','1','-ar',str(sr),'-'])
  samples=np.frombuffer(raw,dtype=np.float32);length=len(samples)/sr;pause=.45 if action!='closing' else 1.2
  timeline.append({'action':action,'text':t,'start':cursor,'speech_duration':length,'duration':length+pause})
  pieces=[v for v in t.replace('？','。').replace('，','。').split('。') if v]
  total=sum(map(len,pieces));offset=0
  for piece in pieces:
   d=length*len(piece)/total
   srt.append(f'{len(srt)+1}\n{stamp(cursor+offset)} --> {stamp(cursor+offset+d)}\n{piece}\n')
   offset+=d
  audio.extend([samples,np.zeros(int(pause*sr),dtype=np.float32)]);cursor+=length+pause
 samples=np.concatenate(audio)
 with wave.open(str(OUT/'narration.wav'),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())
 (OUT/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'subtitles.srt').write_text('\n'.join(srt),encoding='utf-8')
 (OUT/'解说词.txt').write_text('\n\n'.join(t for _,t in SCENES),encoding='utf-8')
 print(json.dumps({'duration':cursor,'scenes':timeline},ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
