"""Compose a short owner-review study, never a completed production episode."""
import argparse
import array
import json
import math
from pathlib import Path
import random
import subprocess
import time
import wave

from PIL import Image, ImageDraw

from .config import Settings
from .media import font, logo_for_display, wrapped
from .process import Deadline, probe
from .store import Store, file_hash

SECONDS, FPS = 12, 24
INK, CREAM, ORANGE = '#352164', '#FFF6DF', '#FF632D'


def smooth(x):
    x=max(0,min(1,x));return x*x*(3-2*x)


def typography(frame, logo):
    t=frame/FPS;im=Image.new('RGBA',(1080,1920));d=ImageDraw.Draw(im)
    fonts={n:font(n) for n in [24,30,40,48,56,64,82,102,116,158]}
    # The official asset is composed once, unmodified apart from profile display and scaling.
    d.rounded_rectangle((770,70,1010,215),radius=24,fill=CREAM)
    im.alpha_composite(logo,(790,86))
    d.text((78,108),'KENAL KOPI',font=fonts[30],fill=INK)
    d.text((78,151),'bareng @kopiegon',font=fonts[24],fill=INK)
    start=0 if t<3 else (3 if t<8 else 8);u=t-start
    offset=round(70*(1-smooth(u/.36)))
    if t<3:
        d.text((90,250+offset),'PLOT TWIST:',font=fonts[40],fill=INK)
        d.text((90,315+offset),'KOPI ITU',font=fonts[82],fill=INK)
        # A staggered word reveal answers the question at the same time as the fruit.
        if t>.32:
            k=smooth((t-.32)/.24)
            d.rounded_rectangle((70,415+offset,650,575+offset),radius=32,fill=CREAM)
            d.text((100,420+offset),'BUAH!',font=fonts[116],fill=INK)
        d.rounded_rectangle((280,1450,800,1530),radius=40,fill=CREAM)
        d.text((540,1466),'iya, buah kopi.',font=fonts[40],anchor='mt',fill=INK)
    elif t<8:
        d.text((540,302+offset),'COBA LIHAT',font=fonts[82],anchor='mt',fill=INK)
        d.text((540,406+offset),'DALAMNYA.',font=fonts[102],anchor='mt',fill=INK)
        if t>4:
            a=smooth((t-4)/.45)
            # Arrows point to the revealed seeds, rather than unrelated decoration.
            for x in [400,680]:
                endy=1110;d.line([(540,1380),(x,round(1380+(endy-1380)*a))],fill=INK,width=8)
                if a>.9:d.polygon([(x,endy),(x-17,endy+38),(x+20,endy+31)],fill=INK)
            d.rounded_rectangle((290,1360,790,1464),radius=30,fill=INK)
            d.text((540,1378),'BIJI KOPI',font=fonts[64],anchor='mt',fill=CREAM)
        d.text((540,1540),'Di dalamnya ada',font=fonts[48],anchor='mt',fill=INK)
        d.text((540,1605),'biji kopi.',font=fonts[48],anchor='mt',fill=INK)
    else:
        d.text((540,302+offset),'KENALAN DULU:',font=fonts[56],anchor='mt',fill=INK)
        d.text((540,404+offset),'BIJI KOPI.',font=fonts[116],anchor='mt',fill=INK)
        d.rounded_rectangle((80,1410,1000,1595),radius=34,fill=CREAM)
        d.text((540,1435),'Biji inilah asal',font=fonts[56],anchor='mt',fill=INK)
        d.text((540,1507),'minuman kopimu.',font=fonts[56],anchor='mt',fill=INK)
    d.text((540,1750),'YOUR CUP. YOUR RULES.',font=fonts[30],anchor='mt',fill=INK)
    d.text((540,1805),'Ilustrasi kartun | EGON COFFEE',font=fonts[24],anchor='mt',fill=INK)
    return im


def sound_effects(path):
    rate=48000;data=array.array('h');rng=random.Random(90)
    pops=[(.12,440),(3.04,330),(4.04,660),(8.04,550)]
    for n in range(rate*SECONDS):
        t=n/rate;v=0.
        for start,f in pops:
            x=t-start
            if 0<x<.28:v+=.10*math.exp(-18*x)*math.sin(2*math.pi*(f*x+110*x*x))
        for start in [2.84,7.84]:
            x=t-start
            if 0<x<.28:v+=.035*math.sin(math.pi*x/.28)**2*rng.uniform(-1,1)
        data.append(round(max(-.8,min(.8,v))*32767))
    with wave.open(str(path),'wb') as w:w.setparams((1,2,rate,len(data),'NONE',''));w.writeframes(data.tobytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--parent-job',required=True)
    args=p.parse_args();out=Path(args.folder).resolve();settings=Settings.from_env();store=Store(settings.db_path)
    if (out/'EGON_CARTOON_EXPLAINER_STUDY.mp4').exists():
        raise FileExistsError('Freeze the prior review output; use a new study folder for a revision')
    parent=store.job(args.parent_job);assert parent['status']=='DESIGN_REVIEW'
    bounded=json.loads((out/'BOUNDED_RUN.json').read_text());remaining=bounded['max_seconds']-(time.time()-bounded['started_at_epoch'])
    deadline=Deadline(remaining)
    raw=out/'CARTOON_ANIMATION.mp4';info=probe(settings.ffprobe,raw,deadline)
    assert abs(float(info['format']['duration'])-SECONDS)<1/FPS
    canonical=store.canonical_logo();assert canonical['sha256']=='301dc7c06831daad76a849775ecd7bab2711af7b0ec335ee9c33f9caff1159ad'
    displayed=logo_for_display(canonical,out);logo=Image.open(displayed).convert('RGBA');logo.thumbnail((200,120),Image.Resampling.LANCZOS)
    # Retain design stills before spending time encoding the animated typography.
    for f in [35,112,162,242]:
        native=Image.open(out/f'STILL_{f:03d}.png').convert('RGBA');native.alpha_composite(typography(f-1,logo));native.convert('RGB').save(out/f'COMPOSITION_{f:03d}.jpg',quality=94)
    layerdir=out/'typography';layerdir.mkdir(exist_ok=True)
    # Short group-entry sequences, not a claim of per-word forced alignment.
    images=[];durations=[]
    for a,b in [(0,3),(3,8),(8,12)]:
        moments=[a+i/24 for i in range(12)]+([a+.5] if a!=3 else [3.5,4.0,4.25,4.5])
        for i,t in enumerate(moments):
            end=moments[i+1] if i+1<len(moments) else b
            f=layerdir/f'L-{a}-{i}.png';typography(round(t*FPS),logo).save(f);images.append(f);durations.append(end-t)
    from .media import concat_file
    concat_file(layerdir/'layers.ffconcat',images,durations)
    deadline.run([settings.ffmpeg,'-v','error','-y','-f','concat','-safe','0','-i',layerdir/'layers.ffconcat','-t',str(SECONDS),'-r',str(FPS),'-c:v','qtrle','-pix_fmt','argb',out/'TYPE.mov'],out/'compose.log')
    chunks=[(.12,2.78,'Plot twist! Kopi itu buah.'),(3.55,3.80,'Di dalamnya ada biji kopi.'),(8.12,3.75,'Biji inilah asal minuman kopimu.')]
    voices=[]
    for i,(start,available,text) in enumerate(chunks):
        txt=out/f'voice-{i}.txt';txt.write_text(text);aiff=out/f'voice-{i}.aiff';wav=out/f'voice-{i}.wav'
        deadline.run(['say','-v',settings.tts_voice,'-r','185','-f',txt,'-o',aiff],out/'compose.log')
        duration=float(probe(settings.ffprobe,aiff,deadline)['format']['duration']);speed=max(1,duration/available)
        if speed>1.2:raise ValueError('Rewrite speech rather than unnaturally accelerating it')
        deadline.run([settings.ffmpeg,'-v','error','-y','-i',aiff,'-af',f'atempo={speed},adelay={round(start*1000)}:all=1,apad','-t',str(SECONDS),'-ar','48000','-ac','1',wav],out/'compose.log');voices.append(wav)
        with wave.open(str(wav),'rb') as source:
            samples=array.array('h');samples.frombytes(source.readframes(source.getnframes()))
            assert max(abs(v) for v in samples)>200,'Empty local voice signal'
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    (out/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(start)} --> {stamp(start+available)}\n{text}' for i,(start,available,text) in enumerate(chunks))+'\n')
    sound_effects(out/'ORIGINAL_SFX.wav')
    result=out/'EGON_CARTOON_EXPLAINER_STUDY.mp4'
    command=[settings.ffmpeg,'-v','error','-y','-i',raw,'-i',out/'TYPE.mov']
    for f in voices+[out/'ORIGINAL_SFX.wav']:command+=['-i',f]
    command+=['-filter_complex','[0:v][1:v]overlay=format=auto,format=yuv420p[v];[2:a][3:a][4:a][5:a]amix=inputs=4:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]','-map','[v]','-map','[a]','-t',str(SECONDS),'-r',str(FPS),'-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-movflags','+faststart',result]
    deadline.run(command,out/'compose.log')
    streams=probe(settings.ffprobe,result,deadline);video=next(v for v in streams['streams'] if v['codec_type']=='video')
    assert (video['width'],video['height'])==(1080,1920)
    assert abs(float(streams['format']['duration'])-SECONDS)<1/FPS
    assert int(video['nb_frames'])==SECONDS*FPS
    assert file_hash(canonical['path'])==canonical['sha256']
    deadline.run([settings.ffmpeg,'-v','error','-i',result,'-f','null','-'],out/'decode.log')
    changed=[]
    for a,b in [(.3,1.4),(3.1,4.4)]:
        samples=[]
        for t in [a,b]:
            r=subprocess.run([settings.ffmpeg,'-v','error','-ss',str(t),'-i',str(result),'-vf','scale=64:114','-frames:v','1','-f','rawvideo','-pix_fmt','gray','pipe:1'],capture_output=True,check=True,timeout=min(30,deadline.remaining()))
            assert len(r.stdout)==64*114;samples.append(r.stdout)
        difference=sum(abs(x-y) for x,y in zip(*samples))/len(samples[0]);assert difference>.3
        changed.append({'from_seconds':a,'to_seconds':b,'mean_decoded_pixel_difference':difference})
    finalframes=[]
    for i,t in enumerate([1.5,4.65,6.75,10.15],1):
        f=out/f'FINAL_{i:02d}.jpg';deadline.run([settings.ffmpeg,'-v','error','-y','-ss',str(t),'-i',result,'-frames:v','1','-q:v','2',f],out/'compose.log');finalframes.append(f)
    board=Image.new('RGB',(1080,1920))
    for i,f in enumerate(finalframes):
        thumb=Image.open(f);thumb.thumbnail((540,960));board.paste(thumb,(i%2*540,i//2*960))
    board.save(out/'PREVIEW.jpg',quality=94)
    asset=store.register_asset(result,'style_preview','Owner requested colourful cartoon explainer for Gen Z; original Blender geometry, original synth SFX, local TTS, canonical unmodified logo; 12-second STYLE_STUDY, not a publishable production episode.')
    qa={'status':'TECHNICAL_PASS','delivery_scope':'STYLE_STUDY','actual_seconds':SECONDS,'dimensions':[1080,1920],'native_fps':FPS,'encoded_fps':video['r_frame_rate'],'actual_encoded_frames':int(video['nb_frames']),'full_file_decode':'PASS','decoded_motion_checks':changed,'caption_alignment':'Measured local TTS chunks; no word-level alignment claimed','canonical_logo_sha256':canonical['sha256'],'output_sha256':file_hash(result),'owner_review':'PENDING','previous_pilot_visual_review':'OWNER_REJECTED','completed_production_episodes':0,'paid_api_idr':0,'parent_job_id':parent['id'],'asset_id':asset,'published':False,'deployed':False}
    (out/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
    (out/'BRIEF.md').write_text('# EGON colourful cartoon explainer — owner-review study\n\nOwner direction: explainer; colourful cartoon motion; Gen Z. Previous 36-second pilot was visually rejected. This 12-second visual proof is not a 30–60-second production episode or publication approval.\n\nOne learning point: coffee beans are seeds inside coffee fruit. Purple/lime fruit hook → yellow cutaway/seed pointers → mint takeaway. Original geometry, expressive entrance and meaningful reveal; no third-party artwork or paid APIs. Simplified illustration, not anatomical scale or EGON lab evidence.\n\nSource reopened 12 November 2026: [National Coffee Association: What is coffee?](https://www.aboutcoffee.org/origins/what-is-coffee/). No trend, product-specific, health or universal two-seed claim. egon_test_ref=null. This is a visual revision of the same engineering lesson, not a new daily insight.\n\nShort scope is intentional; production defaults and publication guards remain unchanged. Local Indonesian voice is preview TTS. Owner aesthetic/voice/pacing review remains pending.\n')
    with store.connect() as con:store.event(con,parent['id'],'STYLE_STUDY_RENDERED',qa)
    print(json.dumps(qa,ensure_ascii=False))


if __name__=='__main__':main()
