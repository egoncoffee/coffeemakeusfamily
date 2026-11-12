"""Native caption-group motion; no false word-level alignment claims."""
from pathlib import Path
from PIL import Image, ImageDraw
from .media import concat_file, font, wrapped


def overlays(settings, doc, timeline, folder, deadline, has_logo):
    root=folder/'overlays';root.mkdir()
    files,spans=[],[]
    for i,item in enumerate(timeline['captions']):
        shot=doc['shots'][item['shot']]
        im=Image.new('RGBA',(1080,1920));draw=ImageDraw.Draw(im)
        draw.text((88,255),f"{item['shot']+1:02d} / {len(doc['shots']):02d}  •  EKSPLORASI KOPI",font=font(22),fill='#d9f230')
        draw.text((88,305),shot['label'],font=font(60),fill='#fff3db')
        draw.line((90,398,245,398),fill='#ff5012',width=7)
        lines=wrapped(item['text'],draw,font(54))
        # The closing shot leaves space above the cup; keep the small guide unobscured.
        y=540 if shot['scene']=='explore' else 1470
        draw.rounded_rectangle((70,y-28,1010,y+len(lines)*70+23),radius=24,fill=(28,12,52,230))
        for n,line in enumerate(lines):draw.text((540,y+n*70),line,font=font(54),anchor='mt',fill='#fff3db')
        still=root/f'caption-{i:02d}.png';im.save(still)
        span=item['end']-item['start'];enter=min(.25,span/4)
        for frame in range(6):
            u=(frame+1)/6;eased=1-(1-u)**3
            moving=Image.new('RGBA',im.size);layer=im.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*eased)))
            moving.alpha_composite(layer,(0,round(18*(1-eased))))
            path=root/f'caption-{i:02d}-enter-{frame:02d}.png';moving.save(path)
            files.append(path);spans.append(enter/6)
        files.append(still);spans.append(span-enter)
    concat_file(root/'captions.ffconcat',files,spans)
    deadline.run([settings.ffmpeg,'-v','error','-y','-f','concat','-safe','0','-i',root/'captions.ffconcat','-t',str(timeline['duration']),'-r',str(settings.output_fps),'-c:v','qtrle','-pix_fmt','argb',folder/'captions.mov'],folder/'render.log')
    brand=Image.new('RGBA',(1080,1920));draw=ImageDraw.Draw(brand)
    draw.text((88,100),'EGON COFFEE',font=font(25),fill='#fff3db')
    draw.text((88,150),'ANIMASI EDUKASI',font=font(19),fill='#d9f230')
    if has_logo:
        # A separate cream backing preserves contrast without repainting the canonical logo.
        draw.rounded_rectangle((744,56,1020,225),radius=20,fill='#fff3db')
    draw.text((540,1772),'YOUR CUP. YOUR RULES.',font=font(28),anchor='mt',fill='#fff3db')
    draw.text((540,1817),'@kopiegon',font=font(25),anchor='mt',fill='#d9f230')
    if not has_logo:draw.text((88,210),'UJI TEKNIS • LOGO BELUM DIBERIKAN',font=font(22),fill='#ff5012')
    brand.save(folder/'brand-treatment.png')
    def stamp(v):
        ms=round(v*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    (folder/'captions.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(r['start'])} --> {stamp(r['end'])}\n{r['text']}" for i,r in enumerate(timeline['captions']))+'\n')
