---
name: local-photo-museum
description: Create and refine a local walkable photo museum or personal collection gallery using Blender-authored geometry and Unreal Engine, including clickable albums, panorama lighting alignment, native packaging, and motion performance checks. Use for local 3D exhibition spaces, not ordinary photo editing or website portfolios.
---

# Local Photo Museum

把用户批准的照片和收藏组织成可以漫游、点击和翻阅合集的本地展览空间。先确认交付形式：Blender 工程、原生交互程序，或两者。保留用户已确认的操作方向、筛选规则与视觉风格；不把某个作品的冬季、文字、尺寸或排除项强加给新项目。

## 素材与空间

- 先使用明确的照片目录或经过审阅的合集清单；排除和重复版本优先级由当前用户要求决定。筛选只改变生成物，不删除原片。
- 网盘素材先选定合集，再按用户授权下载到本地素材缓存。不要默认扫描整个账号、同步全部文件或上传个人照片。
- 一件展品可作为整个合集的入口；场景用展示贴图，打开合集后按需载入高清图，避免一次载入所有原片。
- 建模前确定动线、展墙密度、挑高、室内外视线和材质尺度。保留留白与可通行宽度；作品数量增加时先考虑合集入口与分区。
- 阅读 [素材与场景契约](references/scene-and-assets.md) 了解目录、ID、展品标签、贴图和 Blender 导出要求。

## 引擎与光照

Blender 适合建模和静态高质量预览。若用户要求光追状态下持续实时漫游，优先考虑游戏引擎；不要用 Cycles/OptiX 的静止收敛结果证明可流畅移动。

选定 Unreal 后，阅读 [原生构建流程](references/unreal-workflow.md)。`assets/unreal-runtime-template/` 提供本作品提取的 C++ 相册、输入、按需解码、配置和场景导入器，是需要用户素材与场景的源码模板，不是预建关卡或完整游戏。

- 以 Lumen 硬件光追和 TSR 为实时渲染起点，分别调内部渲染比例、GI/反射质量和帧率上限。硬件支持、分辨率与目标帧率都要实际核对。
- 先把材质的真实尺度、UV、粗糙度、法线与色彩空间设对，再增加分辨率。照片与金属/木材/石材采用不同材质参数。
- 天空全景的太阳位置必须与 DirectionalLight 同步：反转实际纹理采样旋转，并包含 FBX 坐标变换；UE 主光的 forward 是光线传播方向，与指向太阳相反。
- `scripts/panorama_sun.py` 用实测 FBX 基向量和太阳 UV 计算主光方向。全景 JPEG 是 LDR，太阳坐标可用于方向校准，但不能据此声称拥有 HDR 辐射标定。
- 使用相同全景采样方向处理远处环境与地面过渡；近地面保留真实碰撞和受光。过渡要从多处移动视点检查，不能只为一个镜头成立。

## 验证与交付

阅读 [验证与故障经验](references/validation-and-troubleshooting.md)；执行与本次修改有关的检查。

1. 在实际原生程序里连续走动和转头，核对真实视口分辨率及光追状态，检查持续出画面、地面碰撞、相册打开与翻页。
2. 用真实指针动作验证点击和左右拖动；自动射线命中仅验证场景到相册的连接，不能替代鼠标交互验收。
3. 留下动、静、室内、室外的实际画面及帧时间。`scripts/summarize_csv.py` 读取 Unreal CSV 的真实 FrameTime/GPUTime；引擎 DeltaTime 可能钳制长帧，调试截图保存也可能造成停顿。
4. 精确区分素材检查、编译成功、打包成功、运行成功、自动路线通过和人工交互通过。未运行的模板不能描述为已完成游戏。
5. 交付本地启动入口、使用说明与当前版本检查结果。用户要 GitHub 归档时，使用源码白名单导出，排除个人媒体、真实目录清单、截图、缓存、二进制和日志；只有用户明确要求时才发布到外部仓库。

## 可复用工具

- `scripts/prepare_collections.py`：从批准清单复制 JPEG 到新目录，校验复制字节，只保留运行时字段。
- `scripts/verify_catalogue.py`：核对 ID、相册结构、JPEG 文件头与路径边界；不宣称完成逐张解码检查。
- `scripts/export_blender_scene.py`：在单独的 Blender 后台会话导出世界坐标几何、材质和 FBX 校准物；不保存或改写原 `.blend`。
- `scripts/build_museum.ps1`：用显式引擎、工程、缓存和输出路径构建、导入与可选打包；不会安装引擎或上传仓库。
- `scripts/panorama_sun.py`、`scripts/summarize_csv.py`：光照方向和真实帧时间的确定性辅助工具。
