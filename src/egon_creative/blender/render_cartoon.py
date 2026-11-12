"""Original full-episode colourful explainer, rendered as a bounded frame stream."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).parent))
from render_cartoon_study import build as opening, update as opening_update, rgb, mat, mesh, sphere, line, group, bean, smooth


def visible(root, value):
    for o in [root,*root.children_recursive]:o.hide_render=not value


def cylinder(name,pos,radius,depth,material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=depth,location=pos)
    o=bpy.context.object;o.name=name;o.data.materials.append(material)
    bevel=o.modifiers.new('Soft cartoon edge','BEVEL');bevel.width=.035;bevel.segments=3
    o.modifiers.new('Balanced normals','WEIGHTED_NORMAL')
    for p in o.data.polygons:p.use_smooth=True
    return o


def torus(name,pos,radius,thickness,material):
    bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=12,major_radius=radius,minor_radius=thickness,location=pos)
    o=bpy.context.object;o.name=name;o.data.materials.append(material)
    for p in o.data.polygons:p.use_smooth=True
    return o


def cone(name,pos,material):
    bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=.10,radius2=.40,depth=.66,end_fill_type='NOTHING',location=pos)
    o=bpy.context.object;o.name=name;o.data.materials.append(material)
    o.modifiers.new('Illustrative ceramic shell','SOLIDIFY').thickness=.035
    for p in o.data.polygons:p.use_smooth=True
    return o


def cup(purple,cream):
    profile=[(.43,-.92),(.53,-.86),(.57,-.12),(.56,-.04),(.48,-.04),(.47,-.13),(.43,-.79),(0,-.79),(0,-.92)]
    vv=[];ff=[];n=96
    for r,z in profile:
        for j in range(n):
            a=math.tau*j/n;vv.append((r*math.cos(a),r*math.sin(a),z))
    for i in range(len(profile)-1):
        for j in range(n):ff.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    o=mesh('Original rounded open coffee mug',vv,ff,purple);o.data.materials.append(cream)
    for p in o.data.polygons:
        if 3<=p.index//n<=6:p.material_index=1
    line('Soft mug handle',[(.54+.32*math.sin(math.pi*i/24),0,-.13-.62*i/24) for i in range(25)],purple,.085)
    return o


def extras():
    result={};purple=mat('Soft EGON violet','7857D9');cream=mat('Cream ceramic','FFF4DF');orange=mat('Warm orange accent','FF7138');water=mat('Blue water illustration','55BCEB',.28)
    green=mat('Green coffee','B9D68C');seam=mat('Green seam','60833C');brown=mat('Ground coffee','75422A',.7);dark=mat('Roasted seam','43291F',.6)
    for name in ['green','roast','grind','brew','explore']:
        before=set(bpy.context.scene.objects);data={};root=group('Episode chapter '+name)
        if name=='green':
            cylinder('Illustrative processing tray',(0,0,-.52),1.0,.12,purple)
            seeds=[]
            for i in range(6):
                o=bean('Drying seed '+str(i),green,seam);o.scale=(.46,)*3;seeds.append(o)
            data['seeds']=seeds
            drops=[sphere('Schematic moisture cue',(-.8+i*.15,0,.3),(.035,.035,.065),water) for i in range(12)];data['drops']=drops
        elif name=='roast':
            cylinder('Schematic roast pan',(0,0,-.62),1.0,.11,purple)
            seeds=[];colours=[]
            for i in range(6):
                colour=mat('Roast colour '+str(i),'B9D68C');o=bean('Tumbling roast seed '+str(i),colour,dark);o.scale=(.55,)*3;seeds.append(o);colours.append(colour)
            for side in [-1,1]:line('Cartoon heat cue',[(side*(1.06+.05*math.sin(j)),0,-.5+j*.11) for j in range(13)],orange,.025)
            data.update(seeds=seeds,colours=colours)
        elif name=='grind':
            discs=[]
            for z in [.35,.68]:
                disc=torus('Schematic burr',(0,0,z),.42,.07,cream)
                for i in range(14):
                    a=math.tau*i/14
                    ridge=cylinder('Schematic burr ridge',(.36*math.cos(a),.36*math.sin(a),z+.02),.028,.09,orange)
                    world=ridge.matrix_world.copy();ridge.parent=disc;ridge.matrix_world=world
                discs.append(disc)
            cylinder('Ground coffee collection dish',(0,0,-.75),.76,.10,purple)
            whole=[]
            for i in range(2):
                o=bean('Bean entering grinding diagram '+str(i),brown,dark);o.scale=(.20,)*3;whole.append(o)
            grounds=[sphere('Ground particle '+str(i),(0,0,0),(.025,.025,.025),brown) for i in range(42)]
            data.update(discs=discs,whole=whole,grounds=grounds)
        elif name=='brew':
            cup(purple,cream);cone('One illustrative pour-over dripper',(0,0,.60),cream)
            cylinder('Coffee bed stays in the dripper',(0,0,.83),.30,.04,brown)
            liquid=cylinder('Coffee level',(0,0,-.76),.465,.016,brown)
            line('Brewed coffee entering cup',[(0,0,.27),(0,0,-.07)],brown,.019)
            drops=[sphere('Water drop '+str(i),(0,0,1.2),(.026,.026,.035),water) for i in range(7)]
            data.update(liquid=liquid,drops=drops)
        else:
            # Two distinct stylised tools illustrate what to mention when buying grounds.
            cylinder('French press body',(-.64,0,-.26),.30,.78,mat('Pale blue carafe','D2EEEC'))
            cylinder('French press foot',(-.64,0,-.68),.34,.08,purple)
            cylinder('French press lid',(-.64,0,.18),.34,.08,purple)
            stem=cylinder('Plunger stem',(-.64,0,.42),.025,.50,orange)
            knob=sphere('Plunger knob',(-.64,0,.68),(.10,.10,.08),orange)
            line('Press handle',[(-.93,0,.08),(-1.12,0,.04),(-1.15,0,-.43),(-.93,0,-.53)],purple,.055)
            c=cone('Pour-over tool',(.66,0,-.07),cream)
            cylinder('Pour-over stand',(.66,0,-.48),.38,.09,purple)
            cylinder('Server',(.66,0,-.69),.25,.34,mat('Soft peach server','FFBB8F'))
            data.update(stem=stem,knob=knob)
        created=set(bpy.context.scene.objects)-before
        for o in created:
            if o!=root and o.parent not in created:o.parent=root
        visible(root,False);result[name]=(root,data)
    return result


def update(frame,timeline,base,chapters,fps):
    t=(frame-1)/fps;shot=next((s for s in timeline['shots'] if s['start']<=t<s['end']),timeline['shots'][-1]);u=t-shot['start'];name=shot['scene']
    opening_update(frame,base)
    for root,data in chapters.values():visible(root,False)
    if t<8:return
    scene,halves,seeds,disk,accents,background=base
    for o in halves+seeds+[disk]+accents:visible(o,False)
    root,data=chapters[name];visible(root,True)
    ease=smooth(u/.5);root.location=(0,0,-.15*(1-ease))
    colour={'green':'98E4CB','roast':'FFB2A0','grind':'B5A0FF','brew':'AEE4FA','explore':'98E4CB'}[name]
    background.node_tree.nodes['Flat graphic colour'].inputs['Color'].default_value=rgb(colour)
    cam=scene.camera;cam.data.ortho_scale=5.8-.20*smooth(u/shot['duration']);cam.location=(.08*math.sin(u*.5),-9,3.2 if name=='brew' else (2.0 if name in {'green','roast'} else 1.55))
    cam.rotation_euler=(Vector((0,0,.08))-cam.location).to_track_quat('-Z','Y').to_euler()
    if name=='green':
        for i,o in enumerate(data['seeds']):
            o.location=((i%3-1)*.48,(i//3-.5)*.34,-.18+.35*(1-smooth((u-i*.08)/.7)));o.rotation_euler=(0,.2*(i-2),.08*math.sin(u+i))
        for i,o in enumerate(data['drops']):
            x=(u*.5+i*.17)%1;o.location=(-.82+i*.15,0,.35+x*.7);visible(o,u<3.6);size=.035*(1-x);o.scale=(size,size,size*1.8)
    elif name=='roast':
        mix=smooth((u-.6)/4.5);a=rgb('B9D68C');b=rgb('895234')
        for i,o in enumerate(data['seeds']):
            angle=math.tau*i/6+u*.65;o.location=(.59*math.cos(angle),.32*math.sin(angle),-.22+.09*math.sin(u*3+i));o.rotation_euler=(.15*math.sin(u+i),.35*math.sin(u*1.5+i),angle*.3)
            data['colours'][i].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=tuple(x+(y-x)*mix for x,y in zip(a,b))
    elif name=='grind':
        data['discs'][1].rotation_euler.z=u*3.5
        for i,o in enumerate(data['whole']):
            q=(u*.8+i*.5)%1;o.location=(.06*math.sin(i),0,1.15-.47*q);o.rotation_euler.z=u*.4+i
        for i,o in enumerate(data['grounds']):
            q=(u*1.4+i/42)%1;o.location=(.27*math.sin(i*2.4)*q,.18*math.cos(i*2.4)*q,.28-.95*q)
    elif name=='brew':
        data['liquid'].location.z=-.48+.40*smooth(u/5.5)
        for i,o in enumerate(data['drops']):
            q=(u*1.1+i/7)%1;o.location=(.025*math.sin(i),0,1.32-.47*q)
    else:
        displacement=.20*smooth(u/2.5);data['stem'].location.z=.42-displacement;data['knob'].location.z=.68-displacement


def main():
    p=argparse.ArgumentParser();p.add_argument('--timeline',required=True);p.add_argument('--output',required=True);p.add_argument('--fps',type=int,default=24);p.add_argument('--start-frame',type=int,default=1);p.add_argument('--stills',action='store_true');p.add_argument('--ffmpeg',default='ffmpeg')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);timeline=json.loads(Path(args.timeline).read_text());out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    base=opening();scene=base[0];scene.eevee.taa_render_samples=16
    for o in scene.objects:
        if o.type=='LIGHT' and hasattr(o.data,'use_shadow'):o.data.use_shadow=False
    chapters=extras();total=math.ceil(timeline['duration']*args.fps);scene.render.fps=args.fps
    samples=out/'raw_samples';samples.mkdir(exist_ok=True);keys=sorted(set(round(i*(total-1)/11)+1 for i in range(12)))
    if args.stills:keys=[round((s['start']+s['end'])/2*args.fps)+1 for s in timeline['shots']]
    temporary=out/'working-frame.png';scene.render.filepath=str(temporary)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'ORIGINAL_CARTOON_EPISODE.blend'))
    source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();shared=Path(__file__).with_name('render_cartoon_study.py')
    proof={'visual_style':'cartoon_explainer_v3','dimensions':[1080,1920],'native_fps':args.fps,'full_episode_frames':total,'rendered_start_frame':args.start_frame,'samples':16,'original_assets':True,'source_sha256':source_sha,'shared_assets_sha256':hashlib.sha256(shared.read_bytes()).hexdigest(),'disk_strategy':'One transient PNG streamed to FFmpeg; twelve real render samples retained','semantic_scope':'Schematic educational animation, not equipment specifications, anatomical scale, an EGON physical test or a real-time brewing recipe'}
    (out/'blender-provenance.json').write_text(json.dumps(proof,indent=2))
    if args.stills:
        for i,f in enumerate(keys,1):
            update(f,timeline,base,chapters,args.fps);scene.render.filepath=str(out/f'STILL_{i:02d}.png');bpy.ops.render.render(write_still=True)
        return
    if shutil.disk_usage(out).free<300*1024**2:raise RuntimeError('Insufficient streaming-render headroom')
    log=(out/'stream-encode.log').open('wb');enc=subprocess.Popen([args.ffmpeg,'-v','error','-y','-f','image2pipe','-vcodec','png','-framerate',str(args.fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'rendered-animation.mp4')],stdin=subprocess.PIPE,stderr=log)
    try:
        for f in range(args.start_frame,total+1):
            update(f,timeline,base,chapters,args.fps);scene.render.filepath=str(temporary);bpy.ops.render.render(write_still=True)
            if f in keys:shutil.copyfile(temporary,samples/f'frame-{f:04d}.png')
            enc.stdin.write(temporary.read_bytes())
        enc.stdin.close()
        if enc.wait(timeout=60):raise RuntimeError('Streaming encoder failed')
    except BaseException:enc.kill();enc.wait();raise
    finally:log.close()
    temporary.unlink(missing_ok=True)


if __name__=='__main__':main()
