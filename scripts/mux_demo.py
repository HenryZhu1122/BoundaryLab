from pathlib import Path
import json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
try:import imageio_ffmpeg
except ModuleNotFoundError:
    sys.path.insert(0,str(ROOT.parent/'tmp'/'pydeps'))
    import imageio_ffmpeg

video=json.loads((ROOT/'artifacts/demo/video.json').read_text(encoding='utf-8'))['path']
ff=imageio_ffmpeg.get_ffmpeg_exe()
dest=ROOT/'docs/芯界BoundaryLab_演示.mp4'
style='FontName=Microsoft YaHei,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00151C20,Outline=1,BorderStyle=3,BackColour=&HAA101820,MarginV=14'
subprocess.run([ff,'-y','-v','error','-i',video,'-i',str(ROOT/'artifacts/demo/narration.wav'),
                '-vf',f"subtitles=docs/demo_subtitles.srt:force_style='{style}'",
                '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
                '-c:a','aac','-b:a','128k','-movflags','+faststart','-shortest',str(dest)],cwd=ROOT,check=True)
for t in [8,34,59,76,96]:
    subprocess.run([ff,'-y','-v','error','-ss',str(t),'-i',str(dest),'-frames:v','1',
                    str(ROOT/f'artifacts/qa/demo-frame-{t}.png')],check=True)
print('Demo created:',dest,'bytes:',dest.stat().st_size)
