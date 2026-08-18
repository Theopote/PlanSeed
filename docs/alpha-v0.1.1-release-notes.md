# Alpha v0.1.1 — Release Notes

> Post-v0.1 维护版本 · solver **0.6** · 8.4.1 Irregular Site Pipeline（Engineering）  
> Tag：`v0.1.1-alpha` · 安装包：`PlanSeed_0.1.1_x64-setup.exe`

## PlanSeed Alpha v0.1.1

**平台：** Windows 10/11 x64 only

### 安装

1. 下载 `PlanSeed_0.1.1_x64-setup.exe`
2. 运行安装程序
3. 启动 **PlanSeed**，等待引擎 **已就绪**

### 相对 v0.1.0 的变更

- **SOLVER_VERSION 0.6** — irregular site geometry pipeline 接入 normalize → Guillotine pack rects
- **8.4.1 Engineering** — `buildable_polygon` / `buildable_free_rects`；矩形输入行为不变
- Layout Benchmark Suite v1 + MaxRect qualification gate（**MaxRect 仍 FAILED**，不进 Alpha pool）
- 遗留单 case baseline 刷新（硬约束时代 `valid_rate≈0.36`）
- 走廊邻接修补（ADR-011）— privacy Top-5 穿卧室清零，valid 无回退

### Alpha Stable 默认（未变）

Guillotine + axis-diverse + heuristic + rect + residential-alpha-v1

### Known limitations

与 v0.1.0 相同，并明确：

- **产品默认 geometry 仍为 rect** — irregular site pipeline 已工程接入，**不对外宣称 irregular 已产品化**
- MaxRect / Pareto / CP-SAT — experimental only
- 非规范合规 · 非施工图交付

### 冒烟

```powershell
powershell -File scripts/windows_alpha_smoke.ps1
powershell -File scripts/installer_release_smoke.ps1
```
