"""Export the current approved Blender scene, evaluated geometry and photo IDs.
Run with Blender --background approved.blend --python this_file.py.
All meshes use world coordinates in metres. Three calibration meshes allow the
UE importer to discover FBX axis/scale conversion rather than assume it.
"""
import bpy, json, hashlib, shutil, math, argparse, sys
from pathlib import Path
from collections import defaultdict
from mathutils import Vector

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--panorama',type=Path,required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve()
if (OUT/'scene.json').exists():
    raise RuntimeError('Use a new export directory; scene.json already exists')
if not args.panorama.is_file():
    raise FileNotFoundError(args.panorama)
for sub in ('Meshes', 'Textures'):
    (OUT / sub).mkdir(parents=True, exist_ok=True)
deps = bpy.context.evaluated_depsgraph_get()
source = list(bpy.context.scene.objects)
report = {'version': 1, 'source': 'authored-blender-scene',
          'units': 'metres', 'geometry': [], 'materials': {}, 'exhibits': {},
          'calibration': {}, 'lights': [], 'cameras': [], 'skipped': []}
groups = defaultdict(list)
roots = [o for o in source if o.get('album_id') or o.get('合集ID')]
root_for = {}
for root in roots:
    for child in root.children_recursive:
        root_for[child.name] = root

def key(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]

def material_info(mat):
    ident = 'M_' + key(mat.name if mat else 'default')
    if ident in report['materials']:
        return ident
    data = {'name': mat.name if mat else 'default', 'base_color': [0.6,0.6,0.6],
            'roughness': 0.6, 'metallic': 0.0, 'textures': {}}
    if mat and mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                data['base_color'] = list(node.inputs['Base Color'].default_value)[:3]
                data['roughness'] = float(node.inputs['Roughness'].default_value)
                data['metallic'] = float(node.inputs['Metallic'].default_value)
                data['transmission'] = float(node.inputs['Transmission Weight'].default_value)
                data['emission'] = list(node.inputs['Emission Color'].default_value)[:3]
                data['emission_strength'] = float(node.inputs['Emission Strength'].default_value)
            if node.type == 'TEX_IMAGE' and node.image:
                im = node.image
                tex_id = key(im.name)
                path = OUT / 'Textures' / (tex_id + '.png')
                if not path.exists():
                    original = im.filepath_raw
                    fmt = im.file_format
                    im.filepath_raw = str(path)
                    im.file_format = 'PNG'
                    im.save()
                    im.filepath_raw, im.file_format = original, fmt
                role = 'normal' if 'nor_' in im.name else 'roughness' if 'Rough' in im.name else 'color'
                data['textures'][role] = path.name
                if im.name.startswith('PBR_'):
                    data['wood'] = True
        data['glass'] = '玻璃' in mat.name
        data['snow'] = '雪' in mat.name and '薄冰' not in mat.name
        data['panorama_transition'] = '全景' in mat.name
        data['mineral'] = '矿物' in mat.name or '石膏' in mat.name
        data['terrazzo'] = '磨石' in mat.name
        data['granite'] = '花岗岩' in mat.name
    if mat:
        for flag in ('glass','snow','panorama_transition','mineral','terrazzo','granite'):
            if flag in mat: data[flag]=bool(mat[flag])
    report['materials'][ident] = data
    return ident

for obj in source:
    if obj.hide_render:
        continue
    if obj.type == 'LIGHT':
        report['lights'].append({'name':obj.name,'kind':obj.data.type,
            'position':list(obj.matrix_world.translation),
            'rotation':list(obj.matrix_world.to_euler()),'color':list(obj.data.color),
            'energy':obj.data.energy,'size':getattr(obj.data,'size',0.0),
            'size_y':getattr(obj.data,'size_y',0.0)})
        continue
    if obj.type == 'CAMERA':
        report['cameras'].append({'name':obj.name,'position':list(obj.location),
                                 'rotation':list(obj.rotation_euler),'lens':obj.data.lens})
        continue
    if obj.type not in {'MESH','FONT','CURVE'}:
        continue
    root = root_for.get(obj.name)
    if root:
        name = 'SM_Exhibit_' + key(root.name)
        report['exhibits'][name] = {'album':str(root.get('album_id',root.get('合集ID',''))),
            'photo':str(root.get('photo_id',root.get('照片ID',''))), 'title':str(root.get('album_title',root.get('相册',''))),
            'position':list(root.matrix_world.translation)}
    else:
        # Keep spatially separated architecture batches for Lumen surface cache
        # and frustum culling; no monolithic multi-material building mesh.
        coll = obj.users_collection[0].name if obj.users_collection else 'other'
        cell = tuple(int(math.floor(v/12)) for v in obj.matrix_world.translation[:2])
        name = 'SM_Batch_' + key(coll + str(cell))
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
    if not mesh:
        continue
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active
    # Split each non-exhibit batch by material; exhibit keeps photo + frame
    # together to give one clickable asset, with stable material slots.
    for tri in mesh.loop_triangles:
        mat = mesh.materials[tri.material_index] if tri.material_index < len(mesh.materials) else None
        mid = material_info(mat)
        group = name if root else name + '_' + mid
        coords = [list(obj.matrix_world @ mesh.vertices[i].co) for i in tri.vertices]
        uvs = [list(uv.data[i].uv) for i in tri.loops] if uv else [[0,0],[1,0],[0,1]]
        groups[group].append((coords, uvs, mid))
    evaluated.to_mesh_clear()

# Remove the old scene only in this in-memory export session, never save .blend.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
new_materials = {}
for mid in report['materials']:
    new_materials[mid] = bpy.data.materials.new(mid)

def export_mesh(name, tris, directory):
    vertices, faces, face_uvs, face_mats = [], [], [], []
    mats = list(dict.fromkeys(t[2] for t in tris))
    for coords, uvs, mid in tris:
        start = len(vertices)
        vertices.extend(coords)
        faces.append((start,start+1,start+2))
        face_uvs.extend(uvs)
        face_mats.append(mats.index(mid))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for mid in mats:
        mesh.materials.append(new_materials[mid])
    for poly, index in zip(mesh.polygons,face_mats):
        poly.material_index = index
    uv_layer = mesh.uv_layers.new(name='UVMap')
    for loop, value in zip(uv_layer.data, face_uvs):
        loop.uv = value
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(filepath=str(directory/(name+'.fbx')),
        use_selection=True, object_types={'MESH'}, axis_forward='-Y', axis_up='Z',
        apply_unit_scale=True, bake_anim=False, add_leaf_bones=False,
        mesh_smooth_type='FACE', use_triangles=True, use_mesh_modifiers=False)
    bounds = [[min(v[i] for v in vertices) for i in range(3)],
              [max(v[i] for v in vertices) for i in range(3)]]
    report['geometry'].append({'mesh':name,'file':name+'.fbx','materials':mats,
        'triangles':len(faces),'bounds':bounds, 'exhibit':name in report['exhibits']})
    bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.meshes.remove(mesh)

for name,tris in groups.items():
    export_mesh(name,tris,OUT/'Meshes')

# Known distinct world centers; importer verifies scale and solves a rotation.
for axis, center in [('Origin',(0,0,0)),('X',(3,0,0)),('Y',(0,7,0)),('Z',(0,0,11))]:
    name='SM_Calibration_'+axis
    x,y,z=center
    p=[(x-.1,y-.1,z-.1),(x+.1,y-.1,z-.1),(x+.1,y+.1,z-.1),(x-.1,y+.1,z-.1),
       (x-.1,y-.1,z+.1),(x+.1,y-.1,z+.1),(x+.1,y+.1,z+.1),(x-.1,y+.1,z+.1)]
    fs=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
        (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    mid=material_info(None)
    if mid not in new_materials: new_materials[mid]=bpy.data.materials.new(mid)
    export_mesh(name,[([p[i] for i in f],[[0,0],[1,0],[0,1]],mid) for f in fs],OUT/'Meshes')
    report['calibration'][name]=list(center)

shutil.copy2(args.panorama,OUT/'Textures'/'Panorama.jpg')
(OUT/'scene.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('UE_EXPORT',json.dumps({'mesh_count':len(report['geometry']),
    'exhibits':len(report['exhibits']),'materials':len(report['materials']),
    'triangles':sum(g['triangles'] for g in report['geometry'])}))
