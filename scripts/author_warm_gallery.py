"""Authored curved gallery, furniture and full-aspect photographic displays."""
import bpy,bmesh,math,json,argparse,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--scene',type=Path,required=True)
parser.add_argument('--catalogue',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--height',type=float,default=11.)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if not math.isfinite(args.height) or args.height<6.:raise ValueError('Height must be finite and at least 6 metres')
OUT=args.output.resolve()
if OUT.exists() and any(OUT.iterdir()):raise FileExistsError('Use a new empty output directory')
OUT.mkdir(parents=True,exist_ok=True)
S=json.loads(args.scene.read_text(encoding='utf8'))
C=json.loads(args.catalogue.read_text(encoding='utf8'))
for album in C['albums']:
 for photo in album['photos']:
  if any(not isinstance(photo.get(k),(int,float)) or not math.isfinite(photo[k]) or photo[k]<=0 for k in ('width','height')):
   raise ValueError('Every photo requires positive finite width and height')
HEIGHT=args.height
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
groups={}; records=[]; wall_checks=[];
def material(n):return bpy.data.materials.get(n) or bpy.data.materials.new(n)
def add(o,group):
 o.data.materials.append(material(group));groups.setdefault(group,[]).append(o);return o
def box(pos,dim,group,bevel=.025,angle=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.dimensions=dim;o.rotation_euler.z=angle
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  mod=o.modifiers.new('Soft edges','BEVEL');mod.width=bevel;mod.segments=4
  bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 return add(o,group)
def wallx(y,sign):return sign*(5.8+.7*math.cos(y/5.4*math.pi/2))
# Solid smoothly curved walls with actual volume and rounded top/end edges.
for sign in [-1,1]:
 verts=[];faces=[];N=96
 for i in range(N+1):
  y=-5.4+10.8*i/N;x=wallx(y,sign)
  verts.extend([(x-.17,y,.02),(x+.17,y,.02),(x-.17,y,4.35),(x+.17,y,4.35)])
 for i in range(N):
  a=4*i;b=a+4;faces.extend([(a,b,b+2,a+2),(a+1,a+3,b+3,b+1),(a+2,b+2,b+3,a+3),(a,a+1,b+1,b)])
 faces.extend([(0,2,3,1),(4*N,4*N+1,4*N+3,4*N+2)])
 mesh=bpy.data.meshes.new('Curved solid wall');mesh.from_pydata(verts,[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 o=bpy.data.objects.new('Curved gallery',mesh);bpy.context.collection.objects.link(o);add(o,'Plaster')
 bpy.context.view_layer.objects.active=o;o.select_set(True)
 mod=o.modifiers.new('Soft wall edges','BEVEL');mod.width=.055;mod.segments=4;bpy.ops.object.modifier_apply(modifier=mod.name);o.select_set(False)
 for p in o.data.polygons:p.use_smooth=True
 bm=bmesh.new();bm.from_mesh(o.data);volume=bm.calc_volume(signed=True)
 if volume<=0 or any(not e.is_manifold for e in bm.edges):raise RuntimeError('Wall must be closed with outward normals')
 wall_checks.append({'side':sign,'signed_volume_m3':volume,'closed_manifold':True});bm.free()
# Rounded island seating with upholstered top and a recessed bronze foot.
box((0,.2,.25),(2.5,4.9,.36),'Oak',.17)
box((0,.2,.48),(2.38,4.78,.19),'Linen',.09)
box((0,.2,.1),(2.1,4.5,.15),'Bronze',.055)
# Replace the blank side walls with full-height, thin glass curtain panels.
for sign in [-1,1]:
 for col in range(12):
  y=-11+col*2
  box((sign*12.15,y,HEIGHT/2),(.04,1.91,HEIGHT-.09),'Glass',0)
 for i in range(13):box((sign*12.15,-12+i*2,HEIGHT/2),(.12,.075,HEIGHT),'FacadeFrames',.012)
 for z in [0,HEIGHT]:box((sign*12.15,0,z),(.12,24.12,.075),'FacadeFrames',.012)
# Matching uninterrupted front glazing, retaining the existing walk-in opening.
for sign in [-1,1]:
 boundaries=[2.7,4,6,8,10,12]
 for a,b in zip(boundaries,boundaries[1:]):box((sign*(a+b)/2,-12.15,HEIGHT/2),(b-a-.075,.04,HEIGHT-.09),'Glass',0)
 for x in boundaries:box((sign*x,-12.15,HEIGHT/2),(.075,.12,HEIGHT),'FacadeFrames',.012)
 for z in [0,HEIGHT]:box((sign*7.35,-12.15,z),(9.3,.12,.075),'FacadeFrames',.012)
# The previous blank door lintel becomes a glazed transom as well.
box((0,-12.15,(HEIGHT+4.7)/2),(5.31,.04,HEIGHT-4.7-.09),'Glass',0)
for z in [4.7,HEIGHT]:box((0,-12.15,z),(5.4,.12,.075),'FacadeFrames',.012)
# A level gallery perimeter supports browsing the newly accessible rear facade.
box((0,14.9,-.035),(24.7,5.2,.08),'Paving',.008)
for sign in [-1,1]:box((sign*13.775,2.75,-.035),(3.05,29.5,.08),'Paving',.008)
# Fluted oak rear wall: subtle depth undulation, backed by the existing masonry.
for i in range(101):
 x=-11.35+i*.227;depth=.085+.035*math.cos(x*.8)
 box((x,11.99-depth/2,HEIGHT/2),(.095,depth,HEIGHT-.2),'Oak',.016)
# Two authored suspended oval luminaires with soft timber outside and luminous soffits.
for rx,ry,z in [(8.7,7.7,7.25+HEIGHT-8),(3.7,3.0,6.83+HEIGHT-8)]:
 for group,z0,z1,width in [('Oak',z,z+.22,.17),('Light',z-.012,z,.11)]:
  vs=[];fs=[];N=160
  for i in range(N):
   a=2*math.pi*i/N
   vs.extend([((rx-width/2)*math.cos(a),(ry-width/2)*math.sin(a),z0),((rx+width/2)*math.cos(a),(ry+width/2)*math.sin(a),z0),((rx-width/2)*math.cos(a),(ry-width/2)*math.sin(a),z1),((rx+width/2)*math.cos(a),(ry+width/2)*math.sin(a),z1)])
  for i in range(N):
   a=4*i;b=4*((i+1)%N);fs.extend([(a,b,b+1,a+1),(a+2,a+3,b+3,b+2),(a,a+2,b+2,b),(a+1,b+1,b+3,a+3)])
  me=bpy.data.meshes.new('Oval luminaire');me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(group+' oval',me);bpy.context.collection.objects.link(o);add(o,group)
# Fill this fixed six-bank design using approved representatives only.
# Covers repeat when there are fewer albums; the complete catalogue is unchanged.
representatives=[]
for album in C['albums']:
 candidates=[dict(v,mesh=k) for k,v in S['exhibits'].items() if v['album']==album['id']][:2]
 representatives.extend(candidates)
if not representatives:raise ValueError('No approved scene exhibits match catalogue albums')
selected=[dict(representatives[i%len(representatives)]) for i in range(72)]
# Give the window-side corridors their own front-facing, clickable displays.
# Reuse only approved album representatives; the collection catalogue is unchanged.
selected.extend(selected[24:48]+selected[:24])
selected.extend(selected[:24]) # rear facade has a photo face on both sides
selected.extend(dict(v,mesh=k) for k,v in S['exhibits'].items() if next(g for g in S['geometry'] if g['mesh']==k)['bounds'][1][1]<-13)
dims={p['id']:(p['width'],p['height']) for a in C['albums'] for p in a['photos']}
for i,item in enumerate(selected):
 bank=i//24;j=i%24;col=j%8;row=j//8
 curved=bank in (0,1,3,4)
 side='rear_oak'
 if curved:
  sign=-1 if bank in (0,3) else 1;y=-4.7+col*(9.4/7);z=1.14+row*1.28
  # Local display normal -Y turns inward to +X (left), -X (right).
  ang=sign*-math.pi/2; dx=sign*(-.7*math.pi/10.8*math.sin(y/5.4*math.pi/2));ang-=math.atan(dx)
  outward=bank>=3
  if outward:ang+=math.pi
  front=(math.sin(ang),-math.cos(ang))
  x=wallx(y,sign)+front[0]*.245;y+=front[1]*.245
  side=('outward_' if outward else 'inward_')+('left' if sign<0 else 'right')
 elif bank==2:x=-9.45+col*2.7;y=11.7;z=1.55+row*1.55;ang=0
 elif bank==5:x=-9.45+col*2.7;y=12.44;z=1.55+row*1.55;ang=math.pi;side='rear_external'
 else:
  g=next(g for g in S['geometry'] if g['mesh']==item['mesh']);lo,hi=g['bounds']
  x=-7.22;y=(lo[1]+hi[1])/2;z=(lo[2]+hi[2])/2;ang=-math.pi/2;side='courtyard_back'
 w,h=dims[item['photo']];scale=min((1.13 if curved or bank>=6 else 1.9)/w,(1.06 if curved or bank>=6 else 1.3)/h);w*=scale;h*=scale
 clearance=None
 if curved:
  # Sample the full back of the oriented frame against the actual curved volume.
  face_sign=sign if outward else -sign
  clearance=min(face_sign*(x+u*(w+.12)*math.cos(ang)-front[0]*.0325-wallx(y+u*(w+.12)*math.sin(ang)-front[1]*.0325,sign))-.17 for u in [k/64-.5 for k in range(65)])
  if clearance<.015 or z+(h+.12)/2>4.295:raise RuntimeError('Frame intersects wall or rounded top')
 box((x,y,z),(w+.12,.065,h+.12),'Frames',.035,ang)
 # Position front face away from the wall. Full 0..1 UVs retain the entire photograph.
 front=(math.sin(ang),-math.cos(ang));px=x+front[0]*.037;py=y+front[1]*.037
 verts=[]
 for u,v in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]:verts.append((px+u*w*math.cos(ang),py+u*w*math.sin(ang),z+v*h))
 me=bpy.data.meshes.new('Photo');me.from_pydata(verts,[],[(0,1,2,3)]);me.update();uv=me.uv_layers.new()
 for k,co in enumerate([(0,0),(1,0),(1,1),(0,1)]):uv.data[k].uv=co
 o=bpy.data.objects.new('Photo_'+str(i),me);bpy.context.collection.objects.link(o);add(o,'Photo_'+str(i))
 mids=next(g['materials'] for g in S['geometry'] if g['mesh']==item['mesh']);mid=next((m for m in mids if S['materials'][m].get('photo') or S['materials'][m]['name'].lower().startswith(('photo','照片'))),mids[-1])
 records.append({'group':'Photo_'+str(i),'album':item['album'],'photo':item['photo'],'material':mid,'wall_face':side,'frame_back_clearance_m':clearance})
for group,objects in groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.export_scene.fbx(filepath=str(OUT/(group+'.fbx')),use_selection=True,axis_forward='-Y',axis_up='Z',global_scale=1,apply_unit_scale=True,bake_space_transform=False,object_types={'MESH'},use_mesh_modifiers=True,add_leaf_bones=False)
(OUT/'architecture.json').write_text(json.dumps({'groups':list(groups),'displays':records,'curved_walls':2,'wall_geometry_checks':wall_checks,'building_clear_height_m':HEIGHT,'intermediate_glass_transoms':0,'panorama_unchanged_by_this_script':True},ensure_ascii=False,indent=2),encoding='utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WarmGallery.blend'))
