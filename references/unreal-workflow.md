# Unreal 本地构建流程

## 工作工程

把 `assets/unreal-runtime-template/` 复制到仓库之外的专用工作目录；保留模块名 `MomentMuseum`。相邻目录布局：

```text
WorkingMuseum/
  Migration/                 用户自己的导出数据与 scene_settings.json
  MomentMuseum/
    MomentMuseum.uproject
    Source/ Config/ Tools/
    Content/Collections/     用户自己的已批准相册
```

模板没有 `Museum.umap`。必须先准备场景与合集再构建导入；空模板启动不等于完成展馆。引擎源码、引擎插件二进制和照片都未随仓库附带。

使用实际引擎安装目录。原版在 UE 5.8.3 + MSVC 14.44 + Windows SDK 10.0.26100 构建过；这是一组已观察配置，不是其它组合必定失败的要求。编辑器构建依赖适用的 .NET Framework SDK；如果提示 NetFxSDK 缺失，安装相应组件，不能用未经验证的手写替代头文件骗过构建。

默认 `EngineAssociation` 留空，以显式引擎路径构建。PythonScriptPlugin 与 EditorScriptingUtilities 只用于 Editor。选择空间充足的构建和缓存盘；场景资源、PCH、DDC、Zen 与打包暂存都可能占用多 GB。

```powershell
./scripts/build_museum.ps1 -EngineRoot <actual-engine-root> -Project <working-MomentMuseum.uproject> -CacheRoot <large-cache-dir> -Package -ArchiveDirectory <local-game-dir>
```

脚本不安装软件、不处理登录、不创建自动监测，也不上传仓库。首次构建必须编译 Editor target；只有该工程的 Editor 二进制与源码已一致时，才使用 `-SkipEditorBuild`。不要从其它工程拿 DLL 代替。

导入器在专用 `/Game/Museum/Museum` 生成关卡与材质；重新导入会重建这些内容。将手工修改保存在工作副本或单独层级，不把导入当成只读操作。纹理与网格已有资产时会复用；若修改了源文件，需设计重新导入逻辑或换新工作工程，不能假设重新执行会更新所有已有资产。

## 运行时契约

C++ 包含 Character、Controller、Slate 输入面和相册 UI。Actor 标签：

- `MuseumEntry`：入口 PlayerStart；`MuseumGarden`：庭院 TargetPoint；`MuseumAtriumView`：中庭观景点（M）。
- 完整迭代 QA 还使用 `WallCorridorLeft`、`WallCorridorRight`、`RearFacadeView`、`CourtyardBackView`、`CurtainFacadeView`，以及 `MuseumOutdoorExhibit` 和 `WallFace=<face>`。见暖调展馆参考；基础导入器不自动生成这些路线点。
- `MuseumGenerated`：生成物；`MuseumExhibit`、`Album=<id>`、`Photo=<id>`：可点击展品。

照片加载在后台线程解码，Generation 防止快速翻页时旧请求覆盖新图；只保留当前高清纹理。合集目录在打包时作为 NonUFS 文件暂存；仅有导入贴图而缺少 Collections 原 JPEG 时，场景能显示但合集不能完整工作。

操作为 WASD、Shift、鼠标拖动、点击照片、Tab 全部合集、Home 入口、O 庭院、M 中庭、Esc 返回、左右箭头翻页、F8 画质、F9 帧率。拖动方向是模板默认值；新项目以用户要求为准。

## 渲染起点

配置采用 DX12、SM6、Lumen GI/反射、硬件光追、TSR，关闭 Path Tracing 与运动模糊。流畅/画质档的 ScreenPercentage 起点分别为75/100，GI/反射档分别2/3，默认75 FPS上限；需要按目标硬件调节。AA 档 2 配合 TSR history 100% 避免增加历史缓冲分辨率。不要只加渲染比例而忽略历史缓冲、GI、反射与真实 GPUTime。

导入材质将照片设为非镜面纸面，木材等使用独立粗糙度/法线；纹理逐个保存，避免批量保存造成瞬时内存峰值。非二次幂照片可用适当 power-of-two 策略建立 mip 与压缩，但几何比例仍按原照片保留。

太阳算法是当前全景 shader 的逆运算：`uv.x=.5+atan2(y,x)/(2π)`、`uv.y=acos(z)/π`，先反转 lookup yaw，再按实测 FBX basis 转回世界方向。DirectionalLight 的 forward 指向光线传播方向，所以用 `-to_sun` 设置旋转。这个公式不适用于未经转换的 cubemap、其它 UV 约定或任意自定义 shader。

## 验证状态

源码来自已经编译并运行过的原项目；本仓库参数化版本只完成脚本与数据契约检查，尚未在独立全新场景完成 Unreal 再构建。迁移时必须保留这一界限。完整的运行验收方法见 [验证与故障经验](validation-and-troubleshooting.md)。
