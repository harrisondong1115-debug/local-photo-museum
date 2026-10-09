# 素材与场景契约

## 集合

先审阅用户指定素材，形成 `approved.json`：格式与 `assets/catalogue.example.json` 相同，但 `hires_file` 指向批准的素材根目录内的 JPEG 相对路径。重复版本的优先级与排除规则属于当前项目；没有默认排除某个职业、主题或时间段的全局规则。

```powershell
python scripts/prepare_collections.py --manifest approved.json --source-root <approved-photo-root> --output <new-Collections-folder>
python scripts/verify_catalogue.py <Collections-folder>
```

生成的目录再放入工作工程 `Content/Collections/`，结构如下：

```text
Collections/
  catalogue.json
  Photos/<photo-id>.jpg
```

`albums[].id/title/photos` 和 `photos[].id/name` 为运行时字段；ID 使用 ASCII 字母、数字、下划线和短横线。`hires_file` 必须是 `Photos/<id>.jpg`。当前 C++ 实现按照 photo ID 拼接文件名，未实现任意文件路径或 HEIC/RAW/视频播放。同一照片可属于多个合集，但同一个 ID 必须指向同一文件。

准备脚本只复制已批准的 JPEG 并校验字节，不扫描额外目录，不挑选重复版本，不去 EXIF，不重采样。用于公开发布的媒体需要单独决定隐私与许可；本 skill 归档不包含媒体。

## Blender 导出

在原场景的工作副本中组织几何，照片与画框放在同一个展品根对象下。设置根对象自定义属性：`album_id`、`photo_id`，可选 `album_title`；兼容原制作流程的中文属性，但新作品推荐显式英文属性。

材质可设置布尔属性 `glass`、`snow`、`panorama_transition`、`mineral`、`terrazzo`、`granite`。旧中文材质名仍有识别逻辑，显式属性优先。图像节点的角色规则是有限的：图像名含 `nor_` 视为法线、含 `Rough` 视为粗糙度，其余作为颜色；复杂节点网络需要扩展导出器，不能当作完整 Blender 材质转换器。

```powershell
blender --background <working-scene.blend> --python scripts/export_blender_scene.py -- --output <fresh-Migration-dir> --panorama <equirectangular-jpeg>
```

导出器仅在独立后台会话里清空内存场景以写 FBX，不保存 `.blend`。不要在用户交互编辑会话直接运行。场景应使用米；几何烘焙到世界坐标，包含 UV、材质槽与已求值曲线/文字。按空间单元和材质拆分普通几何；展品保持一个可点击对象，避免把整个馆合为大网格。

输出 `Meshes/`、`Textures/`、`scene.json`。四个校准 FBX 的中心分别位于原点与 X=3、Y=7、Z=11 米；导入器用它们测量实际坐标转换。相机信息记录在 JSON 中，当前导入器使用 scene settings 的入口/庭院点而非这些相机。

`scene.json` 的关键字段：

| 字段 | 内容 |
| --- | --- |
| `geometry[]` | mesh、file、materials、triangles、bounds、exhibit |
| `materials` | 按材质 ID 索引的颜色、金属度、粗糙度、纹理与材质标记 |
| `exhibits` | 按网格名索引的 album/photo ID |
| `calibration` | 校准网格名及已知中心位置 |
| `lights[]` | SUN/AREA 类型、位置、Euler 旋转、颜色、尺寸 |

该格式支持这条迁移流程，不包括骨骼、动画、Blender 几何节点实例的任意导入或通用资产库管理。

## 全景与真实地面

把 `assets/scene_settings.example.json` 复制到 `Migration/scene_settings.json`，按场景调整。示例 UV 与 yaw 是虚构值，必须测量自己的全景：`u=(x+0.5)/width`，`v=(y+0.5)/height`。`panorama_lookup_yaw_degrees` 是 shader 采样方向旋转；导入器和太阳反算共用此值。

导出器复制全景到 `Textures/Panorama.jpg`。示例位置是 Blender 世界坐标，单位米；不是固定推荐空间尺寸。入口胶囊中心应离地约0.9米，庭院位置按实际地形调整。

天空球显式设置 NoCollision、禁止 actor collision 和 cast shadow。薄地面需要双面碰撞；双面材质与双面碰撞是两项不同设置。近地面受光、远处渐变到全景时，天空和地面共用采样方向与旋转。从多处视点检验边界与透视；单张全景不提供可随位置移动的远景几何。

JPEG 为 LDR。示例 sky radiance、曝光和光强是起点，需要校准，不是从照片恢复的物理照度。若有真实 HDR/EXR，另行处理动态范围与颜色空间。
