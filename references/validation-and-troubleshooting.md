# 验证与故障经验

这些是原项目观察到的具体问题与处理方法，不保证适用于所有引擎版本。

## 坐标、碰撞与全景

| 症状 | 检查和处理 |
| --- | --- |
| 摄像机被挤到数公里外 | 天空球在保存/重载后可能仍是 BlockAll；显式设 NoCollision profile、NoCollision enabled 与 actor collision false |
| 入口朝向异常 | 用 forward/up 创建旋转，避免 Python Rotator 构造器参数顺序误读 |
| 雪地看得到但角色掉下去 | 逐节启用 collision，检查 complex-as-simple 与薄面 double-sided geometry；two-sided material 不修复碰撞 |
| 太阳明明在右边，阴影却朝右 | 核对实际 shader yaw、FBX 手性、向太阳方向和光线方向的符号；用 UV 反算验证，而非旋转到“看起来差不多” |
| 室内外一转头曝光跳变 | 按设计校准稳定曝光、天空亮度与室内光强；更改预曝光范围只在确有范围警告时处理 |
| 地面与全景只有一个镜头能衔接 | 全景缺乏平移视差，收敛参考点过近；检验多处视点、过渡距离、地形与真实碰撞 |

## 材质与构建

- UE Python 版本变化时，优先查本机对应版本 API。原版 `CustomInput` 与导入材质槽通过 editor properties 设置；粗糙度 TC_MASKS 对应 mask sampler，法线对应 normal sampler。不要把单纯 Python 退出码0当成材质/脚本成功。
- 使用 ASCII 工作工程路径可减少工具链编码问题；保留用户原工程，输出到副本。组件缺失优先修工具链，不修改安全设置。
- 纹理按个保存可降低瞬时提交峰值；不要为了性能一次删除用户资源或全部缓存。避免在空间不足的系统盘重生成巨型 PCH。
- 改关卡/材质但没有改 C++ 时，已一致的 Editor 构建可以复用；先核对再跳过编译。打包时只关闭明确属于当前作品的运行程序，避免广泛结束同名进程。
- 高 DPI 下命令行 ResX/ResY 可能被限制；配置 `bAllowHighDPIInGameMode` 并核对实际渲染视口。`-ForceRes` 是原项目采用的方法，不能根据命令参数就宣称达到分辨率。

## 输入与相册

原版通过透明 Slate 输入面直接处理 FPointerEvent 位移与捕获；每帧轮询光标位置曾遗漏快速拖动。必须测试快速与缓慢左右拖动、按下到释放之间的累积位移，以及点击与拖动的阈值区分。用 geometry local size 到实际 viewport pixels 的比例转换射线坐标，防止 DPI 下点击偏移。

相册首屏没有当前照片时，显示明确选择提示，而不是给空 SImage 画白块。后台加载应防止旧请求盖住新照片；实际检查点开、快速翻页、关闭和重新打开。目录统计成功不等于每张图片完整解码成功。

## 实际运行证据

模板有 `-MuseumQA`，可选 `-MuseumQAQuality`。它在约38秒内执行移动、转头、庭院切换、入口、展品射线命中、相册解码、截图及 Unreal CSV capture，然后退出。它使用模板的展品标签和视线：改变布局后必须调整路线和选图，不能把没有碰到合适展品误判为所有照片功能坏了。

```powershell
<native-game.exe> -MuseumQA -windowed -ForceRes -ResX=2560 -ResY=1600 -unattended -nosplash -NoSound
python scripts/summarize_csv.py <captured-profile.csv>
```

`Saved/MuseumQA/RuntimeQA.json` 应包含实际分辨率、运动帧数、albums/photos、ray_pick_opened_collection、full_photo_decoded、ray tracing supported 及渲染 cvar。截图应显示原关卡内容、正常地面高度和连续运动视角，不是空地图、掉出场景或单张静止渲染。

脚本射线命中与真实鼠标输入分别验证。原生窗口操作使用当前环境支持的应用控制工具，只控制目标游戏；若控制工具授权失败，可继续程序自身的渲染与性能检查，但明确保留未完成的鼠标交互项。

性能记录应包括分辨率、内部渲染比例、质量档、硬件、实际 FrameTime 与 GPUTime、长帧次数和采样范围。Engine DeltaTime 可能钳制长帧；Unreal CSV 中的 debug screenshot 保存停顿也要披露。只报告这一台机器、这一条路线与这一版本观察到的结果，不把60FPS上限、静态渲染耗时或历史项目平均值当作新工程性能验收。

## 公开归档

发布 skill 时仅导出所需文本源码与虚构示例。不要包含个人 JPEG、天空盒原图、相册标题清单、绝对用户名路径、聊天附件标识、运行截图、真实日志、引擎/SDK二进制或任何凭证。README 中明确模板、原项目实测与新项目待验证的差别；未得到具体素材再分发许可时不附带第三方素材。
