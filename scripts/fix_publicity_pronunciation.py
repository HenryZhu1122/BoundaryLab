from pathlib import Path
import asyncio, sys, subprocess, wave, json, shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'tmp/pydeps'))
import edge_tts, imageio_ffmpeg
OUT=ROOT/'artifacts/publicity'
FF=imageio_ffmpeg.get_ffmpeg_exe()
async def main():
    scene=json.loads((OUT/'timeline.json').read_text(encoding='utf8'))[5]
    fixed=OUT/'voice-05-chong.mp3'
    await edge_tts.Communicate(scene['text'].replace('重跑','崇跑'),'zh-CN-YunxiNeural',rate='+18%').save(str(fixed))
    def decode(p,filters=None):
        cmd=[FF,'-v','error','-i',str(p)]
        if filters:cmd+=['-af',filters]
        return np.frombuffer(subprocess.check_output(cmd+['-f','s16le','-ac','1','-ar','24000','-']),dtype='<i2').copy()
    new=decode(fixed); target=round(scene['speech_duration']*24000)
    new=decode(fixed,f'atempo={len(new)/target:.9f}')
    new=np.pad(new,(0,max(0,target-len(new))))[:target]
    original=OUT/'narration-before-pronunciation-fix.wav'
    if not original.exists():shutil.copy2(OUT/'narration.wav',original)
    with wave.open(str(original),'rb') as w:params=w.getparams();samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').copy()
    offset=round(scene['start']*24000);samples[offset:offset+target]=new
    for name in ['narration-chong.wav','narration.wav']:
        with wave.open(str(OUT/name),'wb') as w:w.setparams(params);w.writeframes(samples.tobytes())
    src=ROOT/'docs/芯界BoundaryLab_官微展示_一分钟.mp4'
    dest=ROOT/'docs/芯界BoundaryLab_官微展示_一分钟_发音修正版.mp4'
    subprocess.run([FF,'-y','-v','error','-i',str(src),'-i',str(OUT/'narration-chong.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t','58.802','-movflags','+faststart',str(dest)],check=True)
    subprocess.run([FF,'-v','error','-i',str(dest),'-f','null','-'],check=True)
    shutil.copy2(dest,Path.home()/'Desktop'/dest.name)
    print(json.dumps({'duration':len(samples)/24000,'replacement_start':scene['start'],'replacement_duration':target/24000,'bytes':dest.stat().st_size,'video':'stream copied without reencoding'},ensure_ascii=False))
asyncio.run(main())
