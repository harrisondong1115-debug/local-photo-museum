# 暖调展馆迭代

这是来源作品的一套布局和处理方法，按当前用户要求选用。瀑布已在来源作品中撤销；此模板不添加瀑布特效。

## 空间与光

主体为约 24×24 米，挑高由 8 米增到 11 米。幕墙仅保留竖向细框、顶底边框和必要门洞边框；入口上方为玻璃。提高屋顶时同步抬升后墙、饰面、吊灯与天花光源，避免旧压顶或横杆遗留。照片仍放在可浏览高度，曲面展墙约 4.35 米高，增加挑高不等于把照片移到屋顶。

暖色由橡木、亚麻、香槟金属和大面积柔光形成。来源场景采用六盏 3700 K 矩形天花灯和两盏 4100 K 洗墙灯，矩形面光替代尖锐点光。抬高灯后重新校准照度；来源作品天花灯抬到 10.3 米，每盏调至 320000 lm，这些数值依赖场景尺度与曝光，不能直接当成新场景的通用照度。

室外天空与室内日光仍使用同一全景方向。LDR 雪山照片不包含可靠的 HDR 光强；保留已校准的太阳方向，再调面积、天空填充、曝光及室内灯。不要用全白材质、简单球体或粗糙巨大法线替代真实雪地细节。

## 实墙的两面与穿模

来源作品要求所有实墙展示照片，其他围护改为玻璃。实墙两面单独放置展品；门窗和合理结构边缘按建筑用途保留。来源作品为室内 120、室外 60 个合集入口；入口可复用同一批准封面，不代表新增私人媒体。

曲面墙是闭合实体，重算法线后检查 manifold 边和正的 signed volume。双面材质不会修复反转法线、漏面或穿模。画框朝向由局部墙面切线决定，沿对应面的法线偏移；采样整个画框背板到曲墙的最小间距，同时检查顶边离圆角的距离。来源设计偏移 0.245 米、墙半厚 0.17 米，65 个背板采样点实测最小间隙约 3.09 cm。

内外两面的照片使用各自的 Actor 标签：`WallFace=inward_left/right`、`WallFace=outward_left/right`、`WallFace=rear_oak`、`WallFace=rear_external`、`WallFace=courtyard_back`。标签用于相册路由和遮挡测试；还需 `MuseumExhibit`、`Album=<id>`、`Photo=<id>`，室外入口附加 `MuseumOutdoorExhibit`。从一侧向另一侧展品射线检查实体墙挡住照片，不能只检查“都能点击”。

围护外新增可浏览照片时，也要扩展平整的可行走地面，检查站立与关闭相册后的胶囊高度。只有画面里看起来平的雪面仍可能导致角色滑落。

## Blender 几何生成

`scripts/author_warm_gallery.py` 提取了这次曲墙、两面画框、竖框幕墙、橡木饰面、座椅、椭圆吊灯和外围步道的建模代码，显式接受路径和挑高。运行在独立的 Blender 后台会话；它清空会话内的场景，输出新 `.blend`、分组 FBX 和 `architecture.json`。不读写原场景，也不修改照片。

```powershell
blender --background --python scripts/author_warm_gallery.py -- --scene <Migration/scene.json> --catalogue <approved-catalogue.json> --output <new-MigrationWarm-folder> --height 11
```

输入来自批准合集与已有迁移 `scene.json`：合集照片需有正数像素 `width/height`，展品需匹配 `album/photo`，几何需有 `bounds/materials`。照片材质可设置 `photo=true`，或以 `Photo` / `照片` 开头；否则使用展品最后一个材质槽，应人工核对。固定布局包含六组 8×3 的照片面，代表封面不足时重复已批准封面。原迁移中 `bounds` 最大 Y 小于 -13 米的展品视为庭院正面，几何脚本为它们追加背面；此约定是该布局专用，换场景时必须调整。

生成物只包含几何及占位材质。`architecture.json` 的 `displays` 给出材料 ID、合集 ID、照片 ID 与墙面标签；它不是基础导入器的 `scene.json`。需要自己的 UE 导入步骤将分组 FBX 绑定至相应照片材质与 PBR 材质、设置碰撞并生成 Actor 标签；基础 `import_museum.py` 不会自动应用这层改造。保留太阳、全景、入口、地面与已有庭院，不要用改造脚本重置这些对象。

非玻璃静态结构可按目标硬件使用 Nanite；玻璃不用 Nanite。照片显示面可关闭 cast shadow 和 visible in ray tracing，但保留可点击射线碰撞；后方实体墙仍需正确碰撞与遮挡。灯具发光面无需阻挡玩家。高精度外部素材按来源许可单独获取，公开仓库不附带下载后的纹理或模型。

## 本模板的 QA 布局

完整 129 秒路线需要上述墙面标签和 `MuseumAtriumView`、`WallCorridorLeft`、`WallCorridorRight`、`RearFacadeView`、`CourtyardBackView`、`CurtainFacadeView`。代码中的庭院位置和每面 24 个展品的遮挡计数来自这套布局。基础模板导入新场景后，要改路线、目标数量与位置再运行；缺少观景点或没有可见展品意味着该路线不适用，不能报告通过。

视觉运行保留截图，性能运行额外加 `-MuseumQAPerf`，避免调试写盘混入漫游帧时间。仍需实测鼠标点击与拖动；自动合集射线检查不能代替输入验证。
