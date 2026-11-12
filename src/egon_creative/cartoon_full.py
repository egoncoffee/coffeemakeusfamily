"""Full-duration cartoon rendering adapter and measured-caption composition."""
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

from .media import concat_file, font, wrapped
from .process import probe
from .store import file_hash


INK,CREAM='#352164','#FFF6DF'


def opening_cache(store,doc,timeline,fps):
    spec=doc.get('opening_asset')
    if not spec:return None
    if fps!=24 or spec.get('duration_seconds')!=8 or spec.get('source_in_seconds')!=0:
        raise ValueError('Opening reuse requires the verified first 8 seconds at native 24fps')
    if [s['scene'] for s in timeline['shots'][:2]]!=['cherry','cherry'] or abs(timeline['shots'][0]['end']-3)>.001 or abs(timeline['shots'][1]['end']-8)>.001:
        raise ValueError('Opening cache does not match the explicitly timed fruit/seed sequence')
    with store.connect() as con:r=con.execute("SELECT * FROM assets WHERE id=? AND kind='generated_animation'",(spec['asset_id'],)).fetchone()
    if not r or r['sha256']!=spec['sha256'] or file_hash(r['path'])!=spec['sha256']:
        raise ValueError('Opening animation missing or changed; never reuse unverified cached media')
    return dict(r)


def animated(store,settings,doc,timeline,folder,deadline):
    from .pipeline import render_lock
    if (settings.animation_fps,settings.output_fps)!=(24,24):
        raise ValueError('Full cartoon renderer currently requires native/encoded 24fps')
    cache=opening_cache(store,doc,timeline,settings.animation_fps);skip=192 if cache else 0
    script=Path(__file__).parent/'blender/render_cartoon.py'
    with render_lock(settings.state_dir/'blender.lock',deadline):
        deadline.run([settings.blender,'--background','--factory-startup','--python-exit-code','1','--python',script,'--','--timeline',folder/'timeline.json','--output',folder,'--fps',str(settings.animation_fps),'--start-frame',str(skip+1),'--ffmpeg',settings.ffmpeg],folder/'blender.log')
    produced=folder/'rendered-animation.mp4';info=probe(settings.ffprobe,produced,deadline);video=next(s for s in info['streams'] if s['codec_type']=='video');total=math.ceil(timeline['duration']*settings.animation_fps)
    if int(video['nb_frames'])!=total-skip:raise RuntimeError('Streamed cartoon frame count mismatch')
    samples=folder/'raw_samples'
    if cache:
        p=probe(settings.ffprobe,cache['path'],deadline);v=next(s for s in p['streams'] if s['codec_type']=='video')
        if (v['width'],v['height'])!=(1080,1920) or v['r_frame_rate']!='24/1' or int(v['nb_frames'])<skip:
            raise ValueError('Cached opening dimensions/fps/frame count do not match')
        deadline.run([settings.ffmpeg,'-v','error','-y','-i',cache['path'],'-i',produced,'-filter_complex',f'[0:v]trim=end_frame={skip},setpts=PTS-STARTPTS[p];[p][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]','-map','[v]','-r',str(settings.output_fps),'-c:v','libx264','-preset','fast','-crf','18','-movflags','+faststart',folder/'animation.mp4'],folder/'render.log')
        for i in range(12):
            frame=round(i*(total-1)/11)+1
            if frame<=skip:
                deadline.run([settings.ffmpeg,'-v','error','-y','-ss',str((frame-1)/24),'-i',cache['path'],'-frames:v','1',samples/f'frame-{frame:04d}.png'],folder/'render.log')
        if file_hash(cache['path'])!=cache['sha256']:raise ValueError('Parent opening changed while rendering')
        (folder/'REUSE_PROVENANCE.json').write_text(json.dumps({'asset_id':cache['id'],'parent_sha256':cache['sha256'],'reused_native_frames':skip,'fresh_native_frames':total-skip,'native_fps':24,'retimed_or_looped':False,'source_preserved':True},indent=2))
    else:produced.rename(folder/'animation.mp4')
    final=probe(settings.ffprobe,folder/'animation.mp4',deadline);v=next(s for s in final['streams'] if s['codec_type']=='video')
    if int(v['nb_frames'])!=total:raise RuntimeError('Combined native frame count mismatch')
    actual=sorted(samples.glob('frame-*.png'))
    if len(actual)!=12:raise RuntimeError('Twelve actual motion-review samples are required')
    return actual


def caption_image(doc,item,timeline):
    im=Image.new('RGBA',(1080,1920));d=ImageDraw.Draw(im);shot=timeline['shots'][item['shot']];index=item['shot']
    d.rounded_rectangle((78,248,550,298),radius=25,fill='#DDF84C')
    d.text((103,258),f'{index+1:02d}  DARI BUAH KE CANGKIR',font=font(24),fill=INK)
    lines=wrapped(shot['label'],d,font(76),880)
    for i,text in enumerate(lines):d.text((540,345+i*94),text,font=font(76),anchor='mt',fill=INK)
    if index==1:
        for x in [400,680]:
            d.line([(540,1330),(x,1110)],fill=INK,width=8);d.polygon([(x,1110),(x-17,1145),(x+18,1140)],fill=INK)
        d.rounded_rectangle((355,1290,725,1365),radius=28,fill=INK);d.text((540,1302),'BIJI KOPI',font=font(48),anchor='mt',fill=CREAM)
    if index==6:
        for x,text in [(315,'French press'),(765,'Pour-over')]:
            d.rounded_rectangle((x-200,1220,x+200,1292),radius=24,fill=CREAM);d.text((x,1235),text,font=font(40),anchor='mt',fill=INK)
    body=wrapped(item['text'],d,font(48),840);y=1470
    d.rounded_rectangle((76,y-25,1004,y+len(body)*66+22),radius=32,fill=CREAM)
    for i,text in enumerate(body):d.text((540,y+i*66),text,font=font(48),anchor='mt',fill=INK)
    return im


def overlays(settings,doc,timeline,folder,deadline,has_logo):
    root=folder/'overlays';root.mkdir();files=[];durations=[]
    for i,item in enumerate(timeline['captions']):
        im=caption_image(doc,item,timeline);span=item['end']-item['start'];enter=min(.24,span/4)
        for k in range(6):
            q=(k+1)/6;e=1-(1-q)**3;layer=im.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*e)));moving=Image.new('RGBA',im.size);moving.alpha_composite(layer,(0,round(18*(1-e))))
            path=root/f'C{i:02d}-E{k}.png';moving.save(path);files.append(path);durations.append(enter/6)
        path=root/f'C{i:02d}.png';im.save(path);files.append(path);durations.append(span-enter)
    concat_file(root/'captions.ffconcat',files,durations)
    deadline.run([settings.ffmpeg,'-v','error','-y','-f','concat','-safe','0','-i',root/'captions.ffconcat','-t',str(timeline['duration']),'-r',str(settings.output_fps),'-c:v','qtrle','-pix_fmt','argb',folder/'captions.mov'],folder/'render.log')
    brand=Image.new('RGBA',(1080,1920));d=ImageDraw.Draw(brand)
    d.text((78,100),'KENAL KOPI',font=font(30),fill=INK);d.text((78,149),'bareng @kopiegon',font=font(24),fill=INK)
    if has_logo:d.rounded_rectangle((744,56,1020,225),radius=24,fill=CREAM)
    d.text((540,1770),'YOUR CUP. YOUR RULES.',font=font(30),anchor='mt',fill=INK);d.text((540,1822),'Ilustrasi kartun | EGON COFFEE',font=font(24),anchor='mt',fill=INK)
    brand.save(folder/'brand-treatment.png')
    def stamp(v):
        ms=round(v*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    (folder/'captions.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(r['start'])} --> {stamp(r['end'])}\n{r['text']}" for i,r in enumerate(timeline['captions']))+'\n')
