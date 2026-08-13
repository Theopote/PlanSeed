# Alpha v0.1.0 — Release Notes

> Gate A/B1/C 手测已于 2026-08-14 关门。配合 `scripts/publish_github_release.ps1` 发布。  
> Tag 建议：`v0.1.0` 或 `v0.1.0-alpha`（与脚本 `PLANSEED_RELEASE_TAG` 一致）。

## PlanSeed Alpha v0.1.0

**平台：** Windows 10/11 x64 only

### 安装

1. 下载 `PlanSeed_0.1.0_x64-setup.exe`
2. 运行安装程序
3. 启动 **PlanSeed**（开始菜单）
4. 等待左栏引擎显示 **已就绪**

### 本版本能做什么

- 自然语言 / 表单 → RequirementSpec → 独栋住宅平面生成（Alpha Stable：Guillotine · axis-diverse · rect）
- 多候选比较、布局锁、几何 nudge、设计报告预览与导出
- SVG / PNG（resvg）/ DesignReport JSON 导出
- `.planseed` 项目包导入导出
- 本地 Ollama 需求解析（可选）

### Known limitations

- **Windows 10/11 x64 only** — 无 macOS / Linux 装包
- **独栋住宅 Alpha** — 非多户型 / 非商业建筑产品
- **矩形场地 Alpha geometry** — irregular site 非产品支持（8.4.1 backlog）
- **MaxRect / Pareto / CP-SAT** — experimental / research，非默认路径
- **本地 Ollama 可选** — 无云端 LLM；解析质量依赖本机模型
- **非规范合规** — 不退线 / 面积等不构成法规结论
- **非施工图交付** — 无 BIM / 无施工详图

### 冒烟（可选）

引擎已就绪后：

```powershell
powershell -File scripts/windows_alpha_smoke.ps1
```

### 反馈

Alpha 早期测试版本；问题请附 `engine.log`（Tauri `app_log_dir`）与复现步骤。
