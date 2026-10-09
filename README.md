# Local Photo Museum Skill

把照片与收藏制作成本地可漫游的个人博物馆：Blender 场景制作、Unreal 原生交互、点击展品打开合集、环境全景、光追方向对齐与运行性能验证。

这是从一个已完成本地构建和短路线测试的作品整理出的 **Codex skill 与源码模板**。仓库不含个人照片、全景原图、真实相册目录、已编译游戏或 Unreal 引擎；不能下载后直接当作完整展馆启动。

## 安装为 skill

把整个仓库目录命名为 `local-photo-museum`，复制到 Codex 的 `skills` 目录，例如：

```text
~/.codex/skills/local-photo-museum/SKILL.md
```

重开会话后使用：

```text
使用 $local-photo-museum，把我批准的照片合集做成一个本地现代展馆。
每件展品点开是合集；保留我指定的照片排除规则与鼠标方向。
先整理素材和场景，再构建并实际测试漫游。
```

也可直接让代理读取本仓库 `SKILL.md`。仓库内已有 `agents/openai.yaml`，支持正常自动选择。

## 内容

| 目录 | 用途 |
| --- | --- |
| `SKILL.md` | 工作流程与边界 |
| `references/` | 素材契约、构建流程、踩坑与验收方法 |
| `scripts/` | 集合准备、Blender 导出、构建、太阳方向和帧时间工具 |
| `assets/unreal-runtime-template/` | C++ 漫游、Slate 相册、输入、JPEG 按需解码、UE 配置与导入器 |
| `assets/*.example.json` | 完全虚构的格式示例，不含真实媒体 |

## 使用源码模板

将模板复制到**仓库之外的独立工作目录**，在那里加入自己的素材、生成关卡和程序。构建步骤见 [原生构建流程](references/unreal-workflow.md)，素材格式见 [场景契约](references/scene-and-assets.md)。

普通 Python 工具只依赖标准库。场景导出需要 Blender 的 `bpy`；场景导入需要 Unreal Editor 的 Python 插件；Windows C++ 构建需要相应引擎、MSVC、Windows SDK 和适用的 .NET Framework SDK。

来源工程在 Windows、Blender 4.5 LTS、UE 5.8.3 上编译和运行过。归档里的参数化辅助脚本经过本地校验；**没有对这份公开模板重新执行完整 Unreal 构建**。其他引擎版本需重新验证 API 和插件兼容性。历史硬件性能不作为新场景的帧率承诺。

## 准备上传 GitHub

本仓库只打包白名单文本源码。`.gitignore` 防止常见照片、引擎资产、缓存与构建结果误入，但它不能替代检查 Git 暂存区，尤其对已经被跟踪的文件无效。不要将私人工作目录整体复制进来。

仓库没有远程地址或凭证，也没有自动推送步骤。当前未添加 LICENSE；上传前可按用途选择许可证。Epic/Blender 及第三方素材的二进制和素材未随本仓库分发。

## 本地校验

```powershell
python -B scripts/self_check.py
```

该检查使用虚构数据验证集合复制、路径边界、全景太阳反算和 CSV 长帧统计，不会启动引擎或读取真实相册。归档过程还在 Blender 后台实际导出了一个虚构场景，确认原 `.blend` 未被改写；这不代替 Unreal 的新工程构建与漫游测试。
