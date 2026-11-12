"""Original colourful explainer motion study; deliberately separate from production.

Run in Blender. A streamed image pipe bounds disk use to one temporary frame,
the review stills and the encoded clip. No external models, art or paid service.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

import bpy
from mathutils import Vector

FPS, SECONDS = 24, 12


def rgb(value):
    v = tuple(int(value[i:i+2], 16)/255 for i in (0, 2, 4))
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in v)+(1,)


def mat(name, colour, rough=.4, emission=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=rgb(colour)
    p.inputs['Roughness'].default_value=rough
    if emission:
        e=m.node_tree.nodes.new('ShaderNodeEmission');e.name='Flat graphic colour'
        e.inputs['Color'].default_value=rgb(colour);e.inputs['Strength'].default_value=1
        m.node_tree.links.new(e.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
    else:
        p.inputs['Coat Weight'].default_value=.12
        p.inputs['Coat Roughness'].default_value=.28
    return m


def mesh(name, verts, faces, material):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o)
    data.materials.append(material)
    for p in data.polygons:p.use_smooth=True
    return o


def sphere(name, pos, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=40,location=pos)
    o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(material)
    for p in o.data.polygons:p.use_smooth=True
    return o


def line(name, points, material, width=.018):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=width;c.bevel_resolution=4
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for p,co in zip(s.points,points):p.co=(*co,1)
    o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);c.materials.append(material)
    return o


def group(name):
    o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);return o


def fruit_half(side, red, pulp, stemmat):
    root=group('Original rounded fruit half '+str(side));verts=[];faces=[]
    # A rounded oval cherry, rather than a low-poly stretched primitive.
    n,m=48,64;lo=-math.pi/2 if side>0 else math.pi/2
    for i in range(n+1):
        th=.001+(math.pi-.002)*i/n
        for j in range(m+1):
            ph=lo+math.pi*j/m;r=math.sin(th)
            verts.append((.74*r*math.cos(ph),.64*r*math.sin(ph),.90*math.cos(th)))
    for i in range(n):
        for j in range(m):
            k=i*(m+1)+j;faces.append((k,k+m+1,k+m+2,k+1))
    skin=mesh('Clay red coffee cherry skin',verts,faces,red);skin.parent=root
    skin.data.materials.append(pulp)
    mod=skin.modifiers.new('Soft visible fruit flesh','SOLIDIFY');mod.thickness=.075;mod.material_offset=1
    bevel=skin.modifiers.new('Rounded cut edge','BEVEL');bevel.width=.015;bevel.segments=3
    # A light flesh ring makes the opening legible; not a scientific scale model.
    vv=[];ff=[]
    for i in range(97):
        a=2*math.pi*i/96
        for r in [1,.72]:vv.append((-.012*side,.61*r*math.cos(a),.86*r*math.sin(a)))
    for i in range(96):ff.append((2*i,2*i+2,2*i+3,2*i+1))
    rim=mesh('Illustrative pale fruit flesh ring',vv,ff,pulp);rim.parent=root
    if side>0:
        stem=line('Cherry stem',[(.025,0,.84),(.11,0,1.12),(.23,0,1.22)],stemmat,.04);stem.parent=root
        leafverts=[];leaffaces=[]
        for i in range(25):
            u=i/24;width=.20*math.sin(math.pi*u)
            for sign in [-1,1]:leafverts.append((.15+.67*u,-.025-.10*math.sin(math.pi*u),1.12+.08*u+sign*width))
        for i in range(24):leaffaces.append((2*i,2*i+1,2*i+3,2*i+2))
        leaf=mesh('Original soft coffee leaf',leafverts,leaffaces,stemmat);leaf.parent=root
        mod=leaf.modifiers.new('Leaf thickness','SOLIDIFY');mod.thickness=.018
    return root


def bean(name, material, seam_material):
    root=group(name);vv=[];ff=[];n,m=48,64
    for i in range(n+1):
        a=.001+(math.pi-.002)*i/n;z=.56*math.cos(a)
        for j in range(m):
            b=2*math.pi*j/m;x=.275*math.sin(a)*math.cos(b);y=.20*math.sin(a)*math.sin(b)
            centre=.024*math.sin(z*6)
            if y<0:y+=.075*math.exp(-((x-centre)/.048)**2)*(-math.sin(b))**4
            vv.append((x,y,z))
    for i in range(n):
        for j in range(m):
            k=i*m+j;ff.append((k,k+m,(i+1)*m+(j+1)%m,i*m+(j+1)%m))
    o=mesh(name+' soft grooved seed',vv,ff,material);o.parent=root
    seam=line('Inset seed crease',[(.024*math.sin(z*6),-.126*math.sqrt(max(.05,1-(z/.56)**2)),z) for z in [-.43+.086*i for i in range(11)]],seam_material,.012);seam.parent=root
    return root


def smooth(v):
    v=max(0,min(1,v));return v*v*(3-2*v)


def spring(v):
    v=max(0,min(1,v));return 1-math.exp(-7*v)*math.cos(10*v)


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene
    s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=32
    s.eevee.use_raytracing=False
    s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.fps=FPS
    s.render.image_settings.compression=15
    s.view_settings.view_transform='Standard';s.view_settings.look='None'
    s.world=bpy.data.worlds.new('Soft neutral studio');s.world.use_nodes=True
    s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.8,.8,.8,1)
    s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.30
    red=mat('EGON cherry coral','FF473E',.30);pulp=mat('Warm ivory flesh','FFE5AA',.48)
    leaf=mat('Fresh lime green','98E14D',.4);seed=mat('Light green coffee seed illustration','D1E59D',.4)
    ink=mat('Seed groove green','659343',.48)
    halves=[fruit_half(-1,red,pulp,leaf),fruit_half(1,red,pulp,leaf)]
    beans=[bean('Original seed '+str(i),seed,ink) for i in range(2)]
    # Seamless lit backdrop. Colour changes are part of the explanation's chapters.
    backmat=mat('Changing colourful backdrop','AE93FF',emission=True)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,3,0),rotation=(math.pi/2,0,0))
    bpy.context.object.data.materials.append(backmat)
    # A graphic disk adds a simple sunburst silhouette; it never becomes a logo.
    bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=1.58,depth=.035,location=(0,1.8,.08),rotation=(math.pi/2,0,0))
    disk=bpy.context.object;disk.name='Original lime explainer disk';disk.data.materials.append(mat('Disk lime','DDF84C',emission=True))
    accentmat=mat('Orange concept accent','FF6B24',emission=True)
    accents=[]
    for k in range(6):
        a=math.pi*2*k/6+.3
        o=line('Comic reveal dash',[(math.cos(a)*1.48,.7,math.sin(a)*1.48),(math.cos(a)*1.68,.7,math.sin(a)*1.68)],accentmat,.028);accents.append(o)
    for name,pos,power,size in [('Softbox',(-3,-5,6),380,5),('Cream fill',(4,-3,1),180,4),('Edge highlight',(2,1,4),450,3)]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size
        o.rotation_euler=(Vector((0,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(0,-9,1.5));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=5.9
    cam.rotation_euler=(Vector((0,0,.05))-cam.location).to_track_quat('-Z','Y').to_euler();s.camera=cam
    return s,halves,beans,disk,accents,backmat


def update(frame, data):
    s,halves,beans,disk,accents,backmat=data;t=(frame-1)/FPS
    reveal=smooth((t-3.0)/1.3);close=smooth((t-7.7)/.7)
    entrance=spring(t/.8);bob=.035*math.sin(t*2.2)
    for i,o in enumerate(halves):
        side=-1 if i==0 else 1
        o.location=(side*(.80*reveal+1.2*close)-3.1*(1-entrance),0,bob)
        o.rotation_euler=(.02*math.sin(t),side*.10*reveal,side*.55*reveal)
        o.scale=(1,1+.025*math.sin(t*2),1-.025*math.sin(t*2))
        for part in [o,*o.children_recursive]:part.hide_render=t>=8.45
    for i,o in enumerate(beans):
        side=-1 if i==0 else 1
        for part in [o,*o.children_recursive]:part.hide_render=t<3.05
        o.location=(side*(.22+.18*reveal+.12*close),-.025-.25*close,bob+.03*math.sin(t*2+i))
        sc=1+.32*close;o.scale=(sc,sc,sc)
        o.rotation_euler=(0,side*-.12,side*(.10+.06*math.sin(t*1.8)))
    disk.scale=(1+.025*math.sin(t*1.2),1,1+.025*math.sin(t*1.2))
    disk.rotation_euler.y=0;disk.hide_render=t>=3
    for o in accents:
        o.hide_render=not(3.6<t<6.7);o.scale=(reveal,reveal,reveal)
    colour='AE93FF' if t<3 else ('FFE99F' if t<8 else '98E4CB')
    backmat.node_tree.nodes['Flat graphic colour'].inputs['Color'].default_value=rgb(colour)
    cam=s.camera;cam.data.ortho_scale=5.9-.18*smooth(t/3)-.45*close
    cam.location=(.12*math.sin(t*.45),-9,1.25+.10*math.sin(t*.3))
    cam.rotation_euler=(Vector((0,0,.04))-cam.location).to_track_quat('-Z','Y').to_euler()
    s.frame_set(frame)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--stills',action='store_true');p.add_argument('--ffmpeg',default='ffmpeg')
    p.add_argument('--frame-start',type=int,default=1);p.add_argument('--frame-end',type=int,default=FPS*SECONDS)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    data=build();s=data[0];total=FPS*SECONDS;s.frame_start=1;s.frame_end=total
    temporary=out/'working-frame.png';s.render.filepath=str(temporary)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'ORIGINAL_CARTOON_SCENE.blend'))
    assert 1<=args.frame_start<=args.frame_end<=total
    proof={'delivery_scope':'STYLE_STUDY','seconds':SECONDS,'frames':total,'rendered_frame_range':[args.frame_start,args.frame_end],'native_fps':FPS,'dimensions':[1080,1920],'engine':'EEVEE','samples':32,'original_assets':True,'paid_api_idr':0,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'previous_style_owner_rejected':True,'semantic_scope':'Coffee beans are seeds inside coffee fruit; simplified illustration, not anatomical scale or EGON laboratory evidence.','disk_strategy':'stream each PNG to FFmpeg; retain only four review stills and one temporary frame'}
    (out/'RENDER_PROVENANCE.json').write_text(json.dumps(proof,indent=2))
    keys=[35,112,162,242]
    if args.stills:
        for f in keys:
            update(f,data);s.render.filepath=str(out/f'STILL_{f:03d}.png');bpy.ops.render.render(write_still=True)
        return
    if shutil.disk_usage(out).free<250*1024**2:raise RuntimeError('Insufficient headroom for bounded style study')
    log=(out/'encode.log').open('wb')
    enc=subprocess.Popen([args.ffmpeg,'-v','error','-y','-f','image2pipe','-vcodec','png','-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'CARTOON_ANIMATION.mp4')],stdin=subprocess.PIPE,stderr=log)
    started=time.monotonic()
    try:
        for f in range(args.frame_start,args.frame_end+1):
            update(f,data);s.render.filepath=str(temporary);bpy.ops.render.render(write_still=True)
            if f in keys:shutil.copyfile(temporary,out/f'STILL_{f:03d}.png')
            enc.stdin.write(temporary.read_bytes())
        enc.stdin.close()
        if enc.wait(timeout=60):raise RuntimeError('Streaming FFmpeg failed')
    except BaseException:
        enc.kill();enc.wait();raise
    finally:log.close()
    temporary.unlink(missing_ok=True);proof['render_elapsed_seconds']=time.monotonic()-started
    (out/'RENDER_PROVENANCE.json').write_text(json.dumps(proof,indent=2))


if __name__=='__main__':main()
