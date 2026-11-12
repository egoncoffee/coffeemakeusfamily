"""Run inside Blender 4.5+: original procedural assets; no borrowed artwork."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

PURPLE = (0.20, 0.055, 0.32, 1)
ORANGE = (1.0, 0.22, 0.025, 1)
CREAM = (0.94, 0.85, 0.68, 1)
BROWN = (0.30, 0.13, 0.065, 1)
GREEN = (0.45, 0.57, 0.28, 1)


def linear_color(color):
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in color[:3]) + (color[3],)


def material(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    m.use_nodes = True
    node = m.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = linear_color(color)
    node.inputs["Roughness"].default_value = .48
    return m


def sphere(name, xyz, scale, mat, collection=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    if collection:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def cube(name, xyz, scale, mat, collection=None, bevel=.12):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("Soft original edges", "BEVEL")
    mod.width, mod.segments = bevel, 3
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    if collection:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def curve(name, points, mat, radius=.025, collection=None):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions, data.bevel_depth, data.bevel_resolution = "3D", radius, 3
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    (collection or bpy.context.scene.collection).objects.link(obj)
    data.materials.append(mat)
    return obj


def library(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    white = material("Warm white", (1, .97, .87, 1))
    ink = material("Espresso ink", (.055, .018, .01, 1))
    bean = material("Nara coffee brown", BROWN)
    purple, orange = material("EGON purple direction", PURPLE), material("EGON orange direction", ORANGE)
    cream = material("Cream studio", CREAM)
    char = bpy.data.collections.new("Nara_BeanGuide_V1")
    bpy.context.scene.collection.children.link(char)
    sphere("Nara original bean silhouette", (0, 0, 2.55), (.52, .37, .77), bean, char)
    for x in [-.19, .19]:
        sphere("Expressive eye", (x, -.325, 2.85), (.13, .08, .18), white, char)
        sphere("Pupil", (x + .025, -.40, 2.85), (.065, .035, .095), ink, char)
        sphere("Eye sparkle", (x + .04, -.432, 2.89), (.022, .015, .028), white, char)
    curve("Original friendly smile", [(-.17 + i * .034, -.365, 2.57 - .06 * math.sin(i / 10 * math.pi)) for i in range(11)], ink, .018, char)
    cube("Purple apron", (0, -.325, 2.17), (.64, .13, .48), purple, char, .09)
    sphere("Orange apron button", (0, -.42, 2.37), (.07, .035, .07), orange, char)
    for side in [-1, 1]:
        curve("Soft arm", [(side * .45, 0, 2.55), (side * .69, -.02, 2.28), (side * .74, -.16, 2.48)], bean, .065, char)
        sphere("Mitten", (side * .74, -.16, 2.48), (.115, .09, .12), cream, char)
        sphere("Tiny boot", (side * .23, -.05, 1.72), (.18, .25, .13), purple, char)
    environment = bpy.data.collections.new("Coffee_Exploration_Studio_V1")
    bpy.context.scene.collection.children.link(environment)
    cube("Rounded cream counter", (0, .35, 1.32), (9, 4, .46), cream, environment, .16)
    cube("Purple counter front", (0, .65, .65), (9, 3.4, .95), purple, environment, .2)
    cube("Warm backdrop", (0, 3.2, 3.8), (16, .2, 13), material("Backdrop cream", (.96, .89, .76, 1)), environment, .1)
    for x, z, size, col in [(-3.3, 4.3, .8, purple), (2.7, 3.8, .65, orange), (3.5, 5, .7, purple)]:
        sphere("Original studio accent", (x, 2.8, z), (size, .12, size), col, environment)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def instance(collection_name, path, name):
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [collection_name]
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = dst.collections[0]
    bpy.context.scene.collection.objects.link(empty)
    return empty


def visible_only(objects, first, last, end_frame):
    for obj in objects:
        for frame, hidden in [(1, True), (max(1, first - 1), True), (first, False), (last, False), (last + 1, True), (end_frame + 1, True)]:
            obj.hide_render = hidden
            obj.keyframe_insert(data_path="hide_render", frame=frame)


def make_props(scene_name, first, last, fps, end_frame):
    before = set(bpy.context.scene.objects)
    red = material("Cherry red", (.83, .075, .045, 1))
    green, brown = material("Green coffee", GREEN), material("Roasted coffee", BROWN)
    purple, orange = material("Purple ceramic", PURPLE), material("Orange highlight", ORANGE)
    cream = material("Ceramic cream", CREAM)
    x, y = .80, -.15
    if scene_name == "cherry":
        for side in [-1, 1]:
            obj = sphere("Coffee fruit shell half", (x, y, 2.7), (.45, .43, .57), red)
            mesh = bmesh.new()
            mesh.from_mesh(obj.data)
            bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v.co.x * side < -.001], context="VERTS")
            mesh.to_mesh(obj.data)
            mesh.free()
            shell = obj.modifiers.new("Stylised fruit skin", "SOLIDIFY")
            shell.thickness = .035
            obj.keyframe_insert(data_path="location", frame=first)
            obj.location.x += side * .42
            obj.keyframe_insert(data_path="location", frame=min(last, first + round(fps * 1.4)))
            obj.keyframe_insert(data_path="location", frame=last)
        for offset in [-.18, .18]:
            sphere("Seeds inside fruit", (x + offset, y, 2.7), (.18, .14, .35), green)
        curve("Fruit stalk", [(x, y, 3.18), (x + .12, y, 3.65)], green, .045)
    elif scene_name in {"green", "roast"}:
        for i in range(6):
            gx, gz = x - .48 + (i % 3) * .48, 2.1 + (i // 3) * .7
            color = green if scene_name == "green" else material("Roast transition " + str(i), GREEN)
            obj = sphere("Coffee seed " + str(i), (gx, y, gz), (.2, .15, .35), color)
            obj.rotation_euler.y = (i - 2) * .15
            obj.keyframe_insert(data_path="rotation_euler", frame=first)
            obj.rotation_euler.y += .35
            obj.keyframe_insert(data_path="rotation_euler", frame=last)
            if scene_name == "roast":
                color.diffuse_color = GREEN
                color.keyframe_insert(data_path="diffuse_color", frame=first)
                base = color.node_tree.nodes.get("Principled BSDF").inputs["Base Color"]
                base.default_value = linear_color(GREEN)
                base.keyframe_insert(data_path="default_value", frame=first)
                color.diffuse_color = BROWN
                color.keyframe_insert(data_path="diffuse_color", frame=last)
                base.default_value = linear_color(BROWN)
                base.keyframe_insert(data_path="default_value", frame=last)
            curve("Bean seam " + str(i), [(gx + .02 * math.sin(j), y - .152, gz - .25 + .05 * j) for j in range(11)], material("Seam " + str(i), (.19, .10, .04, 1)), .015)
    else:
        # Illustrative finished coffee, not a claimed physical EGON test or brewing recipe.
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.58, depth=.78, location=(x, y, 2.03))
        cup = bpy.context.object
        cup.name = "Illustrated coffee cup"
        cup.data.materials.append(purple)
        bevel = cup.modifiers.new("Ceramic roundness", "BEVEL")
        bevel.width, bevel.segments = .08, 3
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.51, depth=.018, location=(x, y, 2.43))
        bpy.context.object.data.materials.append(brown)
        curve("Cup handle", [(x + .55 + .32 * math.sin(i / 20 * math.pi), y, 2.32 - .57 * i / 20) for i in range(21)], purple, .09)
        for i in range(3):
            steam = curve("Stylised steam", [(x - .25 + .25 * i + .055 * math.sin(j / 2), y, 2.52 + j * .07) for j in range(13)], cream, .025)
            steam.keyframe_insert(data_path="location", frame=first)
            steam.location.z = .18
            steam.keyframe_insert(data_path="location", frame=last)
        for i in range(3):
            sphere("Beans beside cup", (x - .45 + i * .36, y - .7, 1.69), (.15, .10, .11), brown)
    created = set(bpy.context.scene.objects) - before
    visible_only(created, first, last, end_frame)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--preview-frame", type=int)
    parser.add_argument("--engine", choices=["EEVEE", "WORKBENCH"], default="EEVEE")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    timeline = json.loads(Path(args.timeline).read_text())
    asset_dir, output = Path(args.asset_dir), Path(args.output)
    asset_dir.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    lib = asset_dir / ("original-coffee-studio-" + code_hash + ".blend")
    # File-based cache is only an optimisation. Production workers are single-process by default.
    if not lib.exists():
        library(lib)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if args.engine == "EEVEE" else "BLENDER_WORKBENCH"
    if args.engine == "EEVEE":
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = 16
        if hasattr(scene.eevee, "use_raytracing"):
            scene.eevee.use_raytracing = False
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = args.fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.background_type = "WORLD"
    scene.world = bpy.data.worlds.new("Cream world")
    scene.world.color = (.94, .86, .73)
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get("Background").inputs["Color"].default_value = (1, .96, .87, 1)
    scene.world.node_tree.nodes.get("Background").inputs["Strength"].default_value = .35
    scene.view_settings.view_transform = "AgX" if args.engine == "EEVEE" else "Standard"
    scene.display.render_aa = "8"
    scene.frame_start, scene.frame_end = 1, math.ceil(timeline["duration"] * args.fps)
    instance("Coffee_Exploration_Studio_V1", lib, "Reusable studio")
    guide = instance("Nara_BeanGuide_V1", lib, "Nara reusable guide")
    guide.location.x = -.68
    guide.scale = (1.05, 1.05, 1.05)
    for frame in range(1, scene.frame_end + 2, 4):
        t = frame / args.fps
        guide.location.z = -.08 + .035 * math.sin(t * 2.3)
        guide.rotation_euler.z = .025 * math.sin(t * 1.9)
        guide.keyframe_insert(data_path="location", frame=frame)
        guide.keyframe_insert(data_path="rotation_euler", frame=frame)
    for eye in guide.instance_collection.objects:
        if eye.name.startswith(("Expressive eye", "Pupil", "Eye sparkle")):
            base = eye.scale.z
            for blink in range(48, scene.frame_end, 96):
                for frame, scale in [(blink, base), (blink + 2, base * .12), (blink + 4, base)]:
                    eye.scale.z = scale
                    eye.keyframe_insert(data_path="scale", frame=frame)
    for shot in timeline["shots"]:
        first = round(shot["start"] * args.fps) + 1
        last = min(scene.frame_end, round(shot["end"] * args.fps))
        make_props(shot["scene"], first, last, args.fps, scene.frame_end)
    for name, xyz, energy, size in [("Soft key", (-4, -6, 8), 500, 6), ("Soft fill", (5, -4, 5), 250, 5), ("Warm rim", (0, 2, 7), 450, 4)]:
        bpy.ops.object.light_add(type="AREA", location=xyz)
        light = bpy.context.object
        light.name = name
        light.data.energy, light.data.shape, light.data.size = energy, "DISK", size
        light.rotation_euler = (Vector((0, 0, 2.4)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=(0, -13, 6.1))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 2.65)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 6.1
    for frame in range(1, scene.frame_end + 2, 12):
        t = frame / args.fps
        camera.location.x = .4 * math.sin(t * .16)
        camera.rotation_euler = (Vector((.05, 0, 2.7)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    scene.camera = camera
    scene.render.filepath = str(output / "frame-")
    bpy.ops.wm.save_as_mainfile(filepath=str(output.parent / "storyboard.blend"))
    (output.parent / "blender-provenance.json").write_text(json.dumps({"blender_version": bpy.app.version_string, "engine": scene.render.engine, "native_animation_fps": args.fps, "frames": scene.frame_end, "asset_library": str(lib), "asset_code_sha256": code_hash, "original_procedural_assets": True, "ctmverse_artwork_copied": False}, indent=2))
    if args.preview_frame:
        scene.frame_set(args.preview_frame)
        scene.render.filepath = str(output / "preview.png")
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
