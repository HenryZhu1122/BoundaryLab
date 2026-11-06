from pathlib import Path
import asyncio,json,subprocess,sys,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
try:
    import edge_tts,imageio_ffmpeg
except ModuleNotFoundError:
    sys.path.insert(0,str(ROOT.parent/'tmp'/'pydeps'))
    import edge_tts,imageio_ffmpeg

SCENES=[
 ('overview','这是芯界，一款面向电路学习与科研的自主实验智能体。下面展示真实研究记录的回放，波形与指标都来自实际电路仿真。'),
 ('setup','工作台先固定性能目标和验收条件。模型通过工具调用提出实验，搜索预算与独立网格验证分别记录。'),
 ('bandwidth','在高频小信号条件下，输出增益下降并产生相位滞后。点击测量点，就能检查原始波形和验收指标。'),
 ('slew','改变幅值后，输出出现斜率限制和非线性失真。智能体继续选择对照实验，区分带宽、压摆率和输出摆幅的影响。'),
 ('refuted','每次测量前，模型登记自己的预测。本次有两次预测被实验反驳。系统保留这些记录，并把新结果返回模型。'),
 ('revision','模型提出的第一轮设计，在独立网格上通过一百三十四个点。系统发现剩余失效，将证据返回模型，触发第二轮参数修订。'),
 ('comparison','原始设计通过八十九个网格点，修订后通过一百三十五个。输出摆幅保持不变，仍有失败条件被如实保留。'),
 ('report','证据包包含工具调用、网表、原始数据和报告。八组冻结评测也显示，固定测试同样有效；作品不宣称全面超越传统方法。'),
 ('closing','芯界用可重跑的实验连接假设与结论。当前结果限于通用行为模型，为专业学习和科研设计提供一套可检查的自主实验流程。'),
]


async def main():
    folder=ROOT/'artifacts'/'demo';folder.mkdir(parents=True,exist_ok=True)
    ff=imageio_ffmpeg.get_ffmpeg_exe();sr=24000
    async def speech(i,text):
        p=folder/f'voice-{i:02}.mp3'
        if not p.exists():
            await edge_tts.Communicate(text,'zh-CN-YunxiNeural',rate='+7%').save(str(p))
        return p
    paths=await asyncio.gather(*(speech(i,t) for i,(_,t) in enumerate(SCENES)))
    track=[np.zeros(sr,dtype=np.float32)];cursor=1.0;timeline=[];srt=[]
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    for i,((action,text),p) in enumerate(zip(SCENES,paths)):
        raw=subprocess.check_output([ff,'-v','error','-i',str(p),'-f','f32le','-ac','1','-ar',str(sr),'-'])
        audio=np.frombuffer(raw,dtype=np.float32)
        duration=len(audio)/sr+1.1
        timeline.append({'action':action,'text':text,'start':cursor,'duration':duration})
        # Split subtitles into spoken sentence-size units, not one long line.
        pieces=[x for x in text.replace('，','。').split('。') if x]
        total=sum(map(len,pieces));offset=0
        for piece in pieces:
            length=(duration-1.1)*len(piece)/total
            srt.append(f'{len(srt)+1}\n{stamp(cursor+offset)} --> {stamp(cursor+offset+length)}\n{piece}\n')
            offset+=length
        track.extend([audio,np.zeros(round(sr*1.1),dtype=np.float32)]);cursor+=duration
    audio=np.concatenate(track)
    with wave.open(str(folder/'narration.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
    (folder/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs'/'demo_subtitles.srt').write_text('\n'.join(srt),encoding='utf-8')
    print(json.dumps({'duration_s':round(cursor,2),'ffmpeg':ff,'scenes':len(timeline)},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
