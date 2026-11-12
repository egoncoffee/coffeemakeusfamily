"""Original object-focused coffee explainer. No reference-site artwork or code."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from render_scene import (material, sphere, cube, curve, library, instance,
                          make_props, visible_only, PURPLE, ORANGE, CREAM, BROWN, GREEN)


def cylinder(name, xyz, radius, depth, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=depth, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    mod = obj.modifiers.new('Soft manufactured edge', 'BEVEL')
    mod.width, mod.segments = .035, 3
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def ring(name, xyz, mat, major=.40, minor=.065):
    bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=12,
                                   major_radius=major, minor_radius=minor, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def extras(name, first, last, fps, end_frame):
    before = set(bpy.context.scene.objects)
    orange = material('Warm process accent', ORANGE)
    cream = material('Warm ceramic', CREAM)
    brown = material('Coffee grounds illustration', BROWN)
    metal = material('Original simplified grinding discs', (.70, .72, .78, 1))
    if name == 'roast':
        for side in [-1, 1]:
            obj = curve('Illustrated heat path', [(.8 + side * .78 + .06 * math.sin(j), 0, 1.85 + .11*j) for j in range(14)], orange, .018)
            obj.keyframe_insert(data_path='location', frame=first)
            obj.location.z = .12
            obj.keyframe_insert(data_path='location', frame=last)
    elif name == 'grind':
        for z in [2.43, 2.66]:
            disc = ring('Simplified annular grinding surface', (.8, 0, z), metal)
            for i in range(16):
                a = i * 2 * math.pi / 16
                ridge = cube('Illustrated grinding ridge', (.8 + .37*math.cos(a), .37*math.sin(a), z + .025), (.17, .028, .035), metal, bevel=.01)
                ridge.rotation_euler.z = a
                world = ridge.matrix_world.copy()
                ridge.parent = disc
                ridge.matrix_world = world
            if z > 2.5:
                disc.keyframe_insert(data_path='rotation_euler', frame=first)
                disc.rotation_euler.z = math.pi * 5
                disc.keyframe_insert(data_path='rotation_euler', frame=last)
        cylinder('Grounds collection dish', (.8, 0, 1.55), .57, .07, cream)
        for i in range(7):
            a = first + round((last-first) * i/10)
            b = min(last, a + round(fps*.85))
            seed = sphere('Roasted seed entering diagram', (.8, 0, 3.30), (.10, .075, .16), brown)
            seed.keyframe_insert(data_path='location', frame=a)
            seed.location.z = 2.48
            seed.keyframe_insert(data_path='location', frame=b)
            visible_only([seed], a, b, end_frame)
        for i in range(24):
            a = first + round(fps*.6) + i * max(1, (last-first-round(fps*.9))//24)
            a = min(a, last-2)
            obj = sphere('Illustrated ground particle', (.8 + .07*math.sin(i), 0, 2.40), (.022, .022, .025), brown)
            obj.keyframe_insert(data_path='location', frame=a)
            obj.location = (.8 + .4*math.sin(i*2.4), .3*math.cos(i*2.4), 1.61)
            obj.keyframe_insert(data_path='location', frame=min(last, a+round(fps*.6)))
            visible_only([obj], a, last, end_frame)
    elif name == 'brew':
        # One schematic pour-over example, not a universal recipe or an EGON equipment claim.
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=.13, radius2=.47, depth=.65, end_fill_type='NOTHING', location=(.8, 0, 3.10))
        cone = bpy.context.object
        cone.name = 'Open schematic coffee dripper'
        cone.data.materials.append(cream)
        cone.modifiers.new('Ceramic shell', 'SOLIDIFY').thickness = .035
        cylinder('Illustrated ground bed', (.8, 0, 3.30), .36, .025, brown)
        curve('Water entering illustrative bed', [(.84+.08*math.sin(j*.4), 0, 3.35+j*.04) for j in range(18)], material('Water illustration', (.66,.84,.96,1)), .018)
        stream = curve('Coffee entering the cup', [(.8, 0, 2.43), (.8, 0, 2.78)], brown, .017)
        stream.data.keyframe_insert(data_path='bevel_depth', frame=first)
        stream.data.bevel_depth = .024
        stream.data.keyframe_insert(data_path='bevel_depth', frame=last)
        water = material('Moving water illustration', (.66,.84,.96,1))
        for i in range(10):
            a = first + i*max(1,(last-first-round(fps*.4))//10)
            b = min(last,a+round(fps*.35))
            drop = sphere('Moving water drop',(.84,0,3.96),(.025,.025,.055),water)
            drop.keyframe_insert(data_path='location',frame=a)
            drop.location.z=3.38
            drop.keyframe_insert(data_path='location',frame=b)
            visible_only([drop],a,b,end_frame)
    created = set(bpy.context.scene.objects) - before
    # Animated particles already have narrower visibility intervals.
    visible_only([o for o in created if not o.name.startswith(('Roasted seed entering', 'Illustrated ground particle', 'Moving water drop'))], first, last, end_frame)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--timeline', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--asset-dir', required=True)
    p.add_argument('--fps', type=int, default=24)
    p.add_argument('--engine', choices=['EEVEE', 'WORKBENCH'], default='EEVEE')
    p.add_argument('--preview-frame', type=int)
    p.add_argument('--start-frame', type=int, default=1)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    timeline = json.loads(Path(args.timeline).read_text())
    output, assets = Path(args.output), Path(args.asset_dir)
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    helper = Path(__file__).with_name('render_scene.py')
    helper_sha = hashlib.sha256(helper.read_bytes()).hexdigest()[:16]
    lib = assets / ('original-coffee-studio-' + helper_sha + '.blend')
    if not lib.exists(): library(lib)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if args.engine=='EEVEE' else 'BLENDER_WORKBENCH'
    if args.engine=='EEVEE':
        scene.eevee.taa_render_samples = 8
        scene.eevee.use_raytracing = False
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.fps = args.fps
    scene.frame_start, scene.frame_end = 1, math.ceil(timeline['duration']*args.fps)
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Original purple explainer world')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.032,.016,.065,1)
    bg.inputs['Strength'].default_value = .4
    purple = material('Dark purple stage', (.12,.07,.21,1))
    cylinder('Original circular teaching stage', (.8,.3,1.26), 2.4, .10, purple)
    # Camera follows the concept. No fixed mascot/counter composition.
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    scene.camera = camera
    for index, shot in enumerate(timeline['shots']):
        first, last = round(shot['start']*args.fps)+1, min(scene.frame_end,round(shot['end']*args.fps))
        if index == 0 and shot['scene']=='cherry':
            before = set(scene.objects)
            sphere('Whole coffee fruit', (.8,0,2.7), (.45,.43,.57), material('Cherry skin',(.83,.075,.045,1)))
            curve('Fruit stalk', [(.8,0,3.22),(.88,0,3.55)],material('Stalk',GREEN),.035)
            visible_only(set(scene.objects)-before,first,last,scene.frame_end)
        elif shot['scene']!='grind':
            previous = set(scene.objects)
            make_props(shot['scene'],first,last,args.fps,scene.frame_end)
            if shot['scene'] in {'brew','explore'}:
                for obj in set(scene.objects)-previous:
                    if obj.name.startswith('Stylised steam'):
                        bpy.data.objects.remove(obj,do_unlink=True)
                    elif shot['scene']=='explore' and obj.name.startswith('Beans beside cup'):
                        bpy.data.objects.remove(obj,do_unlink=True)
        extras(shot['scene'],first,last,args.fps,scene.frame_end)
        if shot['scene']=='explore':
            guide = instance('Nara_BeanGuide_V1',lib,'Small original closing guide')
            guide.scale=(.32,.32,.32)
            guide.location=(.25,-.65,.80)
            visible_only([guide],first,last,scene.frame_end)
            guide.keyframe_insert(data_path='rotation_euler',frame=first)
            guide.rotation_euler.z=.14
            guide.keyframe_insert(data_path='rotation_euler',frame=last)
        scale = {'cherry':3.35,'green':3.50,'roast':3.55,'grind':3.75,'brew':4.40,'explore':4.0}[shot['scene']]
        z = 2.80 if shot['scene']=='brew' else 2.55
        target = Vector((.8,-.08,z))
        for frame,u in [(first,0),(first+(last-first)//2,.5),(last,1)]:
            angle=math.radians(-79+index%2*8+u*9)
            camera.location=target+Vector((6.8*math.cos(angle),6.8*math.sin(angle),3.6))
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=scale*(1-.08*u)
            camera.keyframe_insert(data_path='location',frame=frame)
            camera.keyframe_insert(data_path='rotation_euler',frame=frame)
            camera.data.keyframe_insert(data_path='ortho_scale',frame=frame)
    for name,xyz,power,size in [('Warm key',(-3,-5,7),850,5),('Soft fill',(5,-3,5),450,4),('Edge light',(1,3,6),650,3)]:
        bpy.ops.object.light_add(type='AREA',location=xyz)
        light=bpy.context.object;light.name=name;light.data.energy=power;light.data.shape='DISK';light.data.size=size
        light.rotation_euler=(Vector((.8,0,2.6))-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(output/'frame-')
    if not 1 <= args.start_frame <= scene.frame_end:
        raise ValueError('Start frame must be within the full timeline')
    scene.frame_start=args.start_frame
    bpy.ops.wm.save_as_mainfile(filepath=str(output.parent/'storyboard.blend'))
    provenance={'blender_version':bpy.app.version_string,'engine':scene.render.engine,'visual_style':'focus_explainer_v2','native_animation_fps':args.fps,'frames':scene.frame_end,'rendered_start_frame':args.start_frame,'resolution':[1080,1920],'samples':8,'asset_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],'shared_asset_code_sha256':helper_sha,'original_procedural_assets':True,'reference_artwork_copied':False,'motion':'camera orbit/push, fruit reveal, roast colour transition, schematic grinding and pour-over'}
    (output.parent/'blender-provenance.json').write_text(json.dumps(provenance,indent=2))
    if args.preview_frame:
        scene.frame_set(args.preview_frame);scene.render.filepath=str(output/'preview.png');bpy.ops.render.render(write_still=True)
    else:bpy.ops.render.render(animation=True)

if __name__=='__main__':main()
