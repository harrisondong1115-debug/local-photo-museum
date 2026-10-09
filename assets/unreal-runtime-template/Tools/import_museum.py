"""Run only inside Unreal Editor after compiling MomentMuseumEditor.
Builds native static meshes, PBR materials, collision, lights and collection tags.
Keeps the approved source assets untouched. Idempotent imports replace only the
dedicated /Game/Museum assets and Museum level.
"""
import unreal, json, math, runpy
from pathlib import Path

PROJECT=Path(unreal.Paths.project_dir()).resolve()
PROJECTION=runpy.run_path(str(PROJECT/'Tools'/'panorama_projection.py'))
MIGRATION=PROJECT.parent/'Migration'
SCENE=json.loads((MIGRATION/'scene.json').read_text(encoding='utf-8'))
SETTINGS=json.loads((MIGRATION/'scene_settings.json').read_text(encoding='utf-8'))
ASSETS='/Game/Museum'
LIB=unreal.EditorAssetLibrary
MEL=unreal.MaterialEditingLibrary
AS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SS=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
LS=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
for folder in ('Meshes','Textures','Materials'):
    LIB.make_directory(ASSETS+'/'+folder)

def setprop(obj,name,value):
    obj.set_editor_property(name,value)

def import_asset(file,folder,name,options=None):
    existing=LIB.load_asset(ASSETS+'/'+folder+'/'+name)
    if existing: return existing
    task=unreal.AssetImportTask()
    task.filename=str(file)
    task.destination_path=ASSETS+'/'+folder
    task.destination_name=name
    task.automated=True
    task.replace_existing=True
    task.save=True
    if options: task.options=options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths=task.get_editor_property('imported_object_paths')
    if not paths: raise RuntimeError('Import failed: '+str(file))
    result=LIB.load_asset(paths[0])
    if not result: raise RuntimeError('No imported asset: '+str(paths))
    return result

opts=unreal.FbxImportUI()
setprop(opts,'import_mesh',True)
setprop(opts,'import_as_skeletal',False)
setprop(opts,'import_materials',False)
setprop(opts,'import_textures',False)
setprop(opts,'automated_import_should_detect_type',False)
setprop(opts,'mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
data=opts.static_mesh_import_data
setprop(data,'combine_meshes',True)
setprop(data,'convert_scene',True)
setprop(data,'convert_scene_unit',True)
setprop(data,'force_front_x_axis',True)
setprop(data,'transform_vertex_to_absolute',True)
setprop(data,'generate_lightmap_u_vs',False)
setprop(data,'auto_generate_collision',False)
setprop(data,'normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)

calibration={}
for name,position in SCENE['calibration'].items():
    calibration[name]=import_asset(MIGRATION/'Meshes'/(name+'.fbx'),'Meshes',name,opts)
def center(mesh):
    box=mesh.get_bounding_box()
    return [(box.min.x+box.max.x)/2,(box.min.y+box.max.y)/2,(box.min.z+box.max.z)/2]
origin=center(calibration['SM_Calibration_Origin'])
basis=[]
for axis,distance in [('X',3),('Y',7),('Z',11)]:
    end=center(calibration['SM_Calibration_'+axis])
    column=[(end[i]-origin[i])/distance for i in range(3)]
    length=math.sqrt(sum(v*v for v in column))
    if abs(length-100)>1: raise RuntimeError('FBX unit calibration failed: '+str(column))
    basis.append(column)
if abs(basis[2][2]-100)>1: raise RuntimeError('FBX vertical axis calibration failed')

def xyz(p):
    return unreal.Vector(*[sum(basis[j][i]*p[j] for j in range(3)) for i in range(3)])
def unit(p):
    v=xyz(p)
    length=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
    return unreal.Vector(v.x/length,v.y/length,v.z/length)
def direction(rotation,p=(0,0,-1)):
    x,y,z=rotation; a,b,c=p
    b,c=b*math.cos(x)-c*math.sin(x),b*math.sin(x)+c*math.cos(x)
    a,c=a*math.cos(y)+c*math.sin(y),-a*math.sin(y)+c*math.cos(y)
    a,b=a*math.cos(z)-b*math.sin(z),a*math.sin(z)+b*math.cos(z)
    return unit((a,b,c))
def rot(forward):
    return unreal.MathLibrary.make_rot_from_xz(forward,unreal.Vector(0,0,1))

textures={}
for file in (MIGRATION/'Textures').iterdir():
    tex=import_asset(file,'Textures','T_'+file.stem)
    if file.name==SETTINGS['panorama_file']:
        setprop(tex,'max_texture_size',8192)
    else:
        setprop(tex,'max_texture_size',4096)
        # Keep UVs and the photographed frame's geometry aspect ratio. Building
        # power-of-two GPU textures enables mipmaps, BC compression & streaming.
        setprop(tex,'power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
    # Flush this asset's texture build before queuing the next one. Otherwise
    # SaveDirectory can launch hundreds of builds at once and exhaust commit.
    LIB.save_loaded_asset(tex)
    textures[file.name]=tex

def expr(material,cls,x=0,y=0):
    return MEL.create_material_expression(material,cls,x,y)
def scalar(mat,value):
    node=expr(mat,unreal.MaterialExpressionConstant)
    setprop(node,'r',float(value)); return node
def color(mat,value):
    node=expr(mat,unreal.MaterialExpressionConstant3Vector)
    setprop(node,'constant',unreal.LinearColor(*value[:3],1)); return node
def link(a,b,pin,output=''):
    if not MEL.connect_material_expressions(a,output,b,pin):
        names=MEL.get_material_expression_input_names(b)
        if len(names)==1 and MEL.connect_material_expressions(a,output,b,''):
            return
        raise RuntimeError('Material connection failed: '+pin+' available='+str(names))
def output(node,mat,prop,pin=''):
    if not MEL.connect_material_property(node,pin,prop):
        raise RuntimeError('Material output failed: '+str(prop))
def sample(mat,tex,normal=False):
    node=expr(mat,unreal.MaterialExpressionTextureSample)
    setprop(node,'texture',tex)
    if normal: setprop(node,'sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif tex.get_editor_property('compression_settings')==unreal.TextureCompressionSettings.TC_MASKS:
        setprop(node,'sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    elif not tex.get_editor_property('srgb'):
        setprop(node,'sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    return node
def custom(mat,code,names,kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    node=expr(mat,unreal.MaterialExpressionCustom)
    setprop(node,'code',code)
    setprop(node,'output_type',kind)
    inputs=[]
    for name in names:
        item=unreal.CustomInput()
        item.set_editor_property('input_name',name)
        inputs.append(item)
    setprop(node,'inputs',inputs)
    return node

# Panorama sampling uses the calibrated FBX basis. The configurable equirectangular
# lookup rotation is shared with the inverse sun calculation. Shared by sky and distant snow.
# Convert world direction back into Blender's source axes before lookup.
matrix='; '.join('float b%d=dot(D,float3(%s))'%(j,','.join(str(v/100) for v in basis[j])) for j in range(3))+'; '
pano_code=(matrix+('float a=radians(%s); '%SETTINGS['panorama_lookup_yaw_degrees'])+'float x=cos(a)*b0-sin(a)*b1; float y=sin(a)*b0+cos(a)*b1; '
    'float2 uv=float2(0.5+atan2(y,x)/(2*PI),acos(clamp(b2,-1,1))/PI); '
    'return Texture2DSample(Pano,PanoSampler,uv).rgb;')
sky_tex=textures[SETTINGS['panorama_file']]
def panorama(mat,direction_node):
    tex=expr(mat,unreal.MaterialExpressionTextureObject)
    setprop(tex,'texture',sky_tex)
    node=custom(mat,pano_code,['D','Pano'])
    link(direction_node,node,'D'); link(tex,node,'Pano')
    return node

photo_master=LIB.load_asset(ASSETS+'/Materials/M_PhotoMaster')
if not photo_master:
    photo_master=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_PhotoMaster',ASSETS+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    photo_sample=expr(photo_master,unreal.MaterialExpressionTextureSampleParameter2D)
    setprop(photo_sample,'parameter_name','Photo')
    setprop(photo_sample,'texture',next(t for n,t in textures.items() if n!=SETTINGS['panorama_file']))
    output(photo_sample,photo_master,unreal.MaterialProperty.MP_BASE_COLOR)
    output(scalar(photo_master,0.67),photo_master,unreal.MaterialProperty.MP_ROUGHNESS)
    output(scalar(photo_master,0.17),photo_master,unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(photo_master); LIB.save_loaded_asset(photo_master)
materials={}
for mid,info in SCENE['materials'].items():
    path=ASSETS+'/Materials/'+mid
    mat=LIB.load_asset(path)
    if info['name'].startswith('照片') and 'color' in info.get('textures',{}):
        if not mat:
            mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset(mid,ASSETS+'/Materials',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mat,photo_master)
        MEL.set_material_instance_texture_parameter_value(mat,'Photo',textures[info['textures']['color']])
        LIB.save_loaded_asset(mat); materials[mid]=mat
        continue
    if mat:
        MEL.delete_all_material_expressions(mat)
    else:
        mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset(mid,ASSETS+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    setprop(mat,'two_sided',bool(info.get('snow')))
    base=color(mat,info['base_color'])
    rough=scalar(mat,info['roughness'])
    output(scalar(mat,info['metallic']),mat,unreal.MaterialProperty.MP_METALLIC)
    for role,name in info.get('textures',{}).items():
        tex=textures[name]
        if role=='normal':
            setprop(tex,'srgb',False)
            setprop(tex,'compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
            setprop(tex,'flip_green_channel',True)
            LIB.save_loaded_asset(tex)
            output(sample(mat,tex,True),mat,unreal.MaterialProperty.MP_NORMAL)
        elif role=='roughness':
            setprop(tex,'srgb',False)
            setprop(tex,'compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
            LIB.save_loaded_asset(tex)
            rough=sample(mat,tex)
        else:
            base=sample(mat,tex)
    # Authored world-scale variation avoids stretch on long walls or floors.
    if info.get('terrazzo') or info.get('mineral') or info.get('granite') or info.get('snow'):
        world=expr(mat,unreal.MaterialExpressionWorldPosition)
        if info.get('terrazzo'):
            code=('float2 q=P.xy*0.65; float2 cell=floor(q); float2 f=frac(q)-0.5; '
                  'float h=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453); '
                  'float chip=(1-smoothstep(0.10,0.30,length(f)))*step(0.65,h); '
                  'return lerp(float3(0.50,0.52,0.51),lerp(float3(0.25,0.28,0.29),float3(0.68,0.65,0.59),h),chip);')
        else:
            scale=1.2 if info.get('mineral') else 0.7
            base_values=','.join(str(v) for v in info['base_color'])
            code=('float3 q=floor(P*%s); float h=frac(sin(dot(q,float3(12.9898,78.233,37.719)))*43758.5453); '
                  'return float3(%s)*(0.96+0.08*h);')%(scale,base_values)
        base=custom(mat,code,['P']); link(world,base,'P')
        micro=custom(mat,'float3 q=floor(P*1.5); float h=frac(sin(dot(q,float3(12.9898,78.233,37.719)))*43758.5453); return float3((h-0.5)*0.016,(frac(h*17)-0.5)*0.016,1);',['P'])
        link(world,micro,'P'); output(micro,mat,unreal.MaterialProperty.MP_NORMAL)
    if info.get('glass'):
        setprop(mat,'blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        setprop(mat,'translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        setprop(mat,'two_sided',True)
        base=color(mat,[0.88,0.94,0.98]); rough=scalar(mat,0.06)
        fresnel=expr(mat,unreal.MaterialExpressionFresnel)
        opacity=expr(mat,unreal.MaterialExpressionLinearInterpolate)
        link(scalar(mat,0.018),opacity,'A'); link(scalar(mat,0.34),opacity,'B'); link(fresnel,opacity,'Alpha')
        output(opacity,mat,unreal.MaterialProperty.MP_OPACITY)
        output(scalar(mat,0.5),mat,unreal.MaterialProperty.MP_SPECULAR)
    elif info.get('panorama_transition'):
        world=expr(mat,unreal.MaterialExpressionWorldPosition)
        anchor=xyz(SETTINGS['transition_anchor_metres'])
        anchor_node=color(mat,[anchor.x,anchor.y,anchor.z])
        delta=expr(mat,unreal.MaterialExpressionSubtract); link(world,delta,'A'); link(anchor_node,delta,'B')
        normal=expr(mat,unreal.MaterialExpressionNormalize); link(delta,normal,'VectorInput')
        pano=panorama(mat,normal)
        fade=custom(mat,'return smoothstep(4500,18000,length(P.xy-A.xy));',['P','A'],unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        link(world,fade,'P'); link(anchor_node,fade,'A')
        inv=expr(mat,unreal.MaterialExpressionOneMinus); link(fade,inv,'Input')
        near=expr(mat,unreal.MaterialExpressionMultiply); link(base,near,'A'); link(inv,near,'B'); base=near
        radiance=expr(mat,unreal.MaterialExpressionMultiply)
        link(pano,radiance,'A'); link(scalar(mat,SETTINGS.get('sky_radiance',8000)),radiance,'B')
        far=expr(mat,unreal.MaterialExpressionMultiply); link(radiance,far,'A'); link(fade,far,'B')
        output(far,mat,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    elif info.get('emission_strength',0)>0:
        e=info.get('emission',[1,1,1]); strength=info['emission_strength']
        output(color(mat,[v*strength for v in e]),mat,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    output(base,mat,unreal.MaterialProperty.MP_BASE_COLOR)
    output(rough,mat,unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)
    materials[mid]=mat

if not LS.new_level(ASSETS+'/Museum'):
    if not LS.load_level(ASSETS+'/Museum'): raise RuntimeError('Cannot create Museum level')
    # Replace only generated actors; leave unrelated editor actors intact.
    for actor in AS.get_all_level_actors():
        if actor.actor_has_tag('MuseumGenerated'): AS.destroy_actor(actor)
def spawn(cls,location=unreal.Vector(0,0,0),rotation=unreal.Rotator(0,0,0),label=None):
    actor=AS.spawn_actor_from_class(cls,location,rotation)
    actor.set_actor_location(location,False,False)
    actor.set_actor_rotation(rotation,False)
    actor.tags=['MuseumGenerated']
    if label: actor.set_actor_label(label)
    return actor

for item in SCENE['geometry']:
    name=item['mesh']
    if name in SCENE['calibration']: continue
    mesh=import_asset(MIGRATION/'Meshes'/item['file'],'Meshes',name,opts)
    slots=mesh.get_editor_property('static_materials')
    assigned=set()
    for index,slot in enumerate(slots):
        slot_name=str(slot.get_editor_property('imported_material_slot_name'))
        mid=next((m for m in item['materials'] if slot_name==m or slot_name.startswith(m)),None)
        if mid is None and len(item['materials'])==1: mid=item['materials'][0]
        if mid is None: raise RuntimeError('Unmapped material slot '+name+' '+slot_name)
        mesh.set_material(index,materials[mid]); assigned.add(mid)
    if assigned!=set(item['materials']): raise RuntimeError('Material slot count mismatch: '+name)
    body=mesh.get_editor_property('body_setup')
    for index in range(len(slots)):
        SS.enable_section_collision(mesh,True,0,index)
    if body:
        setprop(body,'collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        setprop(body,'double_sided_geometry',True)
    LIB.save_loaded_asset(mesh)
    actor=spawn(unreal.StaticMeshActor,label=name)
    comp=actor.static_mesh_component
    comp.set_static_mesh(mesh)
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_collision_profile_name('BlockAll')
    if item['exhibit']:
        exhibit=SCENE['exhibits'][name]
        actor.tags=['MuseumGenerated','MuseumExhibit','Album='+exhibit['album'],'Photo='+exhibit['photo']]
    # Thin photo frames and signage still raster-render, but do not add BVH
    # overlap to the lighting rays; photographs retain visibility click traces.
    if item['exhibit']:
        setprop(comp,'visible_in_ray_tracing',False)

sky_mat=LIB.load_asset(ASSETS+'/Materials/M_WinterSky')
if not sky_mat:
    sky_mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_WinterSky',ASSETS+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
MEL.delete_all_material_expressions(sky_mat)
setprop(sky_mat,'two_sided',True)
setprop(sky_mat,'shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
setprop(sky_mat,'is_sky',True)
world=expr(sky_mat,unreal.MaterialExpressionWorldPosition)
cam=expr(sky_mat,unreal.MaterialExpressionCameraPositionWS)
delta=expr(sky_mat,unreal.MaterialExpressionSubtract); link(world,delta,'A'); link(cam,delta,'B')
normal=expr(sky_mat,unreal.MaterialExpressionNormalize); link(delta,normal,'VectorInput')
radiance=expr(sky_mat,unreal.MaterialExpressionMultiply)
link(panorama(sky_mat,normal),radiance,'A'); link(scalar(sky_mat,SETTINGS.get('sky_radiance',8000)),radiance,'B')
output(radiance,sky_mat,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
MEL.recompile_material(sky_mat); LIB.save_loaded_asset(sky_mat)
sky=spawn(unreal.StaticMeshActor,label='User panorama')
sky.static_mesh_component.set_static_mesh(LIB.load_asset('/Engine/BasicShapes/Sphere'))
sky.static_mesh_component.set_material(0,sky_mat)
sky.set_actor_scale3d(unreal.Vector(4000,4000,4000))
sky.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
sky.static_mesh_component.set_collision_profile_name('NoCollision')
sky.set_actor_enable_collision(False)
setprop(sky.static_mesh_component,'cast_shadow',False)
setprop(sky.static_mesh_component,'visible_in_ray_tracing',False)

# Captured panorama provides the ambient colour; physical near snow stays lit
# by Lumen. A soft directional light and broad warm rect lights connect spaces.
sky_light=spawn(unreal.SkyLight,label='Winter ambient light')
sky_light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
setprop(sky_light.light_component,'intensity',0.15)
setprop(sky_light.light_component,'real_time_capture',True)
setprop(sky_light.light_component,'sky_distance_threshold',50000.0)
for item in SCENE['lights']:
    if item['kind']=='SUN':
        # Light rays must originate at the solar disc after the sky's rotation
        # and FBX axis conversion, rather than inheriting a Blender sun angle.
        rays=unreal.Vector(*[-x for x in PROJECTION['sun_direction'](basis,SETTINGS['sun_uv'],SETTINGS['panorama_lookup_yaw_degrees'])])
        actor=spawn(unreal.DirectionalLight,xyz(item['position']),rot(rays),item['name'])
        setprop(actor.light_component,'intensity',12000.0)
        setprop(actor.light_component,'light_source_angle',1.5)
    elif item['kind']=='AREA':
        actor=spawn(unreal.RectLight,xyz(item['position']),rot(direction(item['rotation'])),item['name'])
        setprop(actor.light_component,'intensity_units',unreal.LightUnits.LUMENS)
        setprop(actor.light_component,'intensity',50000.0)
        setprop(actor.light_component,'source_width',max(item['size']*100,20))
        setprop(actor.light_component,'source_height',max(item['size_y']*100,20))
        setprop(actor.light_component,'attenuation_radius',1400.0)
        setprop(actor.light_component,'specular_scale',0.0)
        setprop(actor.light_component,'cast_shadows',False)
    else: continue
    actor.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    actor.light_component.set_light_color(unreal.LinearColor(*item['color'],1))

# Avoid auto-exposure pumping during turns. Camera stays around eye height.
pp=spawn(unreal.PostProcessVolume,label='Winter museum exposure')
setprop(pp,'unbound',True)
settings=pp.settings
settings.override_auto_exposure_method=True
settings.auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL
settings.override_auto_exposure_bias=True
settings.auto_exposure_bias=-1
settings.override_auto_exposure_apply_physical_camera_exposure=True
settings.auto_exposure_apply_physical_camera_exposure=True
settings.override_camera_iso=True; settings.camera_iso=100
settings.override_camera_shutter_speed=True; settings.camera_shutter_speed=125
settings.override_depth_of_field_fstop=True; settings.depth_of_field_fstop=2.8
settings.override_motion_blur_amount=True; settings.motion_blur_amount=0
settings.override_bloom_intensity=True; settings.bloom_intensity=0.15
settings.override_lumen_reflection_quality=True; settings.lumen_reflection_quality=1.0
pp.settings=settings

entry_pos=xyz(SETTINGS['entry_position_metres'])
entry_rot=rot(unit(SETTINGS['entry_forward']))
start=spawn(unreal.PlayerStart,entry_pos,entry_rot,'MuseumEntry')
start.tags=['MuseumGenerated','MuseumEntry']
garden=spawn(unreal.TargetPoint,xyz(SETTINGS['garden_position_metres']),rot(unit(SETTINGS['garden_forward'])),'MuseumGarden')
garden.tags=['MuseumGenerated','MuseumGarden']
LS.save_current_level()
LIB.save_directory(ASSETS,recursive=True,only_if_is_dirty=True)
report={'status':'imported','fbx_basis_cm':basis,'mesh_count':len(SCENE['geometry'])-4,
        'exhibits':len(SCENE['exhibits']),'materials':len(materials),
        'runtime_tested':False,'shipping_game_built':False}
(PROJECT.parent/'ImportReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('MUSEUM_IMPORT_FINISHED '+json.dumps(report))
