from pathlib import Path
import sys, subprocess, json
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'tmp/pydeps'))
import imageio_ffmpeg
FF=imageio_ffmpeg.get_ffmpeg_exe()
OUT=ROOT/'artifacts/publicity/edit'; OUT.mkdir(exist_ok=True)
SRC=Path(r'C:\Users\33943\Desktop\QQ20261101-220345-HD.mp4')
# Original recording only. Cuts remove waiting; retained actions run at original speed.
wide=(440,100,2116,1400)
segments=[
 (1,6.56,wide,'芯界 BoundaryLab','自主实验智能体 · 作者：朱航'),
 (8,6.282,wide,'01  从性能要求出发','真实工作台录屏'),
 (17.8,5.0,wide,'02  启动自主实验','真实运行 · 已剪去等待'),
 (26,4.378,wide,'02  仿真返回测量证据','真实运行 · 已剪去等待'),
 (57,5.2,wide,'03  寻找电路的失效边界','以下为完整研究记录回放'),
 (65,3.386,(500,100,1330,700),'03  点击测量点，检查对应波形','200 kHz / 5 mV · 原始设计'),
 (81.4,5.11,(500,820,1330,660),'04  用实验检验事先预测','20 kHz / 250 mV · 预测被实验反驳'),
 (125,2.9,(500,100,1980,1400),'04  修改方案，独立复测','完整研究记录回放'),
 (94,7.0,wide,'05  相同验收标准，比较优化前后','89 / 165 → 135 / 165 · 原始 → 候选'),
 (127,5.306,(500,100,1980,1400),'05  两轮优化，保留复测证据','通用电路行为模型 · 结果限于采样点'),
 (133,7.68,wide,'芯界，让每一个结论都有实验依据','假设 → 实验 → 证据 → 修正'),
]
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
manifest=[]; elapsed=0
for i,(start,duration,crop,title,note) in enumerate(segments):
    overlay=Image.new('RGBA',(2560,1600),(0,0,0,0));d=ImageDraw.Draw(overlay)
    d.rectangle((0,0,2560,99),fill='#08141e');d.rectangle((0,1452,2560,1600),fill='#08141e')
    d.rectangle((80,27,88,70),fill='#80dfc3')
    d.text((108,24),title,font=font(37),fill='#edf7fa')
    box=d.textbbox((0,0),note,font=font(26)); d.text((2480-(box[2]-box[0]),32),note,font=font(26),fill='#9bb4c3')
    d.line((80,1453,2480,1453),fill='#2e4d59',width=2)
    p=OUT/f'overlay{i:02}.png';overlay.save(p)
    x,y,w,h=crop
    filt=f'[0:v]crop={w}:{h}:{x}:{y},scale=2400:1352:force_original_aspect_ratio=decrease:flags=lanczos,pad=2400:1352:(ow-iw)/2:(oh-ih)/2:color=0x08141e,pad=2560:1600:80:100:color=0x08141e,setsar=1,fps=30[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]'
    dest=OUT/f'clip{i:02}.mp4'
    subprocess.run([FF,'-y','-v','error','-ss',str(start),'-i',str(SRC),'-loop','1','-i',str(p),'-filter_complex',filt,'-map','[out]','-t',str(duration),'-an','-c:v','libx264','-preset','fast','-crf','18','-threads','4',str(dest)],check=True)
    manifest.append(dict(source_start=start,output_start=elapsed,duration=duration,crop=crop,title=title,note=note));elapsed+=duration
    print(f'clip {i+1}/{len(segments)} complete',flush=True)
(OUT/'edit_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'clips.txt').write_text('\n'.join(f"file 'clip{i:02}.mp4'" for i in range(len(segments))),encoding='utf8')
subprocess.run([FF,'-y','-v','error','-f','concat','-safe','0','-i',str(OUT/'clips.txt'),'-c','copy',str(OUT/'silent.mp4')],check=True)
srt=(ROOT/'artifacts/publicity/subtitles.srt').read_text(encoding='utf8').replace('Boundary Lab','BoundaryLab').replace('一百六十五个采样点中的达标点从八十九个提升至一百三十五个','165 个采样点中的达标点，从 89 个提升至 135 个')
(OUT/'captions.srt').write_text(srt,encoding='utf8')
dest=ROOT/'docs/芯界BoundaryLab_官微展示_一分钟.mp4'
style='FontName=Microsoft YaHei,FontSize=19,PrimaryColour=&H00F7FAFC,OutlineColour=&H001E1408,Outline=0.6,Shadow=0,MarginV=12,Alignment=2'
subprocess.run([FF,'-y','-v','error','-i',str(OUT/'silent.mp4'),'-i',str(ROOT/'artifacts/publicity/narration.wav'),'-vf',f"subtitles=captions.srt:force_style='{style}'",'-c:v','libx264','-preset','fast','-crf','18','-threads','4','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','58.802','-movflags','+faststart',str(dest)],cwd=OUT,check=True)
print(str(dest),dest.stat().st_size,flush=True)

