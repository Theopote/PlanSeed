# Phase 7.1 — Desktop Print Smoke（真实打印验收）

> **原则：** CSS 看起来合理 ≠ Windows WebView2 实际打印一定合理。  
> **7.1 关闭前必须完成本表**；继续堆 `@media print` 规则不能代替本验收。  
> 详案总览：[phase-7-deliverables.md](phase-7-deliverables.md)

## 怎么跑

### A. 生成压力 HTML（本机）

```powershell
uv run python scripts/generate_print_smoke_reports.py
```

输出目录：`debug/print-smoke/`（含 `index.html` + 各场景 `.html`）。

浏览器直接打开 HTML → Print → **Microsoft Print to PDF** 也可做第一轮；
**关门验收以 Desktop（Tauri / WebView2）为准**：

1. 启动 Desktop（`pnpm` / `scripts/dev-desktop`）
2. 打开对应项目或把 smoke HTML 内容经「报告」预览路径核对（优先用脚本 HTML 对照版式）
3. 报告预览 → **Print** → **Microsoft Print to PDF**
4. 在 PDF 阅读器里逐项勾选下方检查点

### B. 打印目标

| 项 | 固定 |
|----|------|
| 打印机 | Microsoft Print to PDF |
| 纸张 | A4 |
| 方向 | 纵向（Portrait） |
| 边距 | 默认（勿选手动 0 边距除非记入结果） |
| 缩放 | 默认 100% / Fit（记下实际选项） |

---

## 场景矩阵

对每个场景产出一份 PDF，文件名建议：`7.1-{id}-{pass|fail}.pdf`。

| ID | 场景 | 脚本 fixture | 重点 |
|----|------|--------------|------|
| F1 | 1 层 | `01_floors_1f` | 单平面页、无多余空白页 |
| F2 | 2 层 | `02_floors_2f` | 层间 page-break；SVG 不被拦腰切 |
| F3 | 3 层 | `03_floors_3f` | 多层连续分页；末页无多余空白 |
| N1 | 短项目名 | `04_name_short` | Cover 标题不塌陷 |
| N2 | 超长中文项目名 | `05_name_long_zh` | 标题换行/截断是否可接受 |
| R1 | 大量房间 | `06_many_rooms` | 面积表跨页是否难看 |
| K1 | 大量 Findings | `07_many_findings` | Findings 章节分页 |
| A0 | 无 Assumption | `08_no_assumptions` | 空态文案；附录不占怪页 |
| U1 | 大量 Unknown | `09_many_unknowns` | 列表过长 |
| U2 | blocking Unknown | `10_blocking_unknown` | Cover banner 醒目且不打碎平面 |
| L-en | 英文 locale | `11_locale_en` | 英文字体、北向标签 |
| L-zh | 中文 locale | `12_locale_zh` | 中文字体不丢、不方框 |

脚本一次生成全部 fixture；勾选时按 ID 填结果表。

---

## 每份 PDF 必查（勾选）

对 **每一个** 场景 PDF：

| # | 检查点 | Pass? | 备注 |
|---|--------|-------|------|
| 1 | **无正文截断**（标题 / 表格末行 / Findings） | ☐ | |
| 2 | **无异常空白页**（封面后、层间、文末） | ☐ | |
| 3 | **SVG 平面不被分页切成两半** | ☐ | |
| 4 | **表格跨页**可接受（表头重复更好；至少不切字） | ☐ | |
| 5 | **字体未丢失**（中文不方框；英文不回落怪体） | ☐ | |
| 6 | **北向 / 文字不错位**（未知北向不画假 ↑N；有角度时箭头合理） | ☐ | |
| 7 | **页边距合理**（不贴边、不溢出裁切） | ☐ | |

**场景级总评：** Pass / Fail / Pass-with-notes

---

## 结果记录

| ID | 环境 | 总评 | 失败项 (#) | 日期 | 操作者 |
|----|------|------|------------|------|--------|
| F1 | Desktop WebView2 | | | | |
| F2 | Desktop WebView2 | | | | |
| F3 | Desktop WebView2 | | | | |
| N1 | Desktop WebView2 | | | | |
| N2 | Desktop WebView2 | | | | |
| R1 | Desktop WebView2 | | | | |
| K1 | Desktop WebView2 | | | | |
| A0 | Desktop WebView2 | | | | |
| U1 | Desktop WebView2 | | | | |
| U2 | Desktop WebView2 | | | | |
| L-en | Desktop WebView2 | | | | |
| L-zh | Desktop WebView2 | | | | |

**对照（可选）：** 同一 HTML 用 Edge 打开 Print to PDF，仅作参考；**不得**用 Edge 结果代替 Desktop 关门。

---

## 关门条件（7.1）

- [ ] 上表 **全部场景** 在 Desktop + Microsoft Print to PDF 下有记录  
- [ ] 无 **P0**：SVG 拦腰切断 / 主壳被 `window.print` / 中文字体全面丢失 / blocking banner 不可见  
- [ ] P1（空白页、表跨页丑）记入「已知限制」；**不**用继续堆 CSS 假装已验收  
- [ ] 本页结果表填完后，方可在 [phase-7-deliverables.md](phase-7-deliverables.md) 将 7.1 DoD「真实打印验收」勾完成

**失败分流：**

| 现象 | 归属 |
|------|------|
| iframe/`contentWindow.print` 打出工作台 | P0 → 立刻修 Print fallback（仍属 7.1） |
| 分页/SVG 切页/空白页 | 记结果；小修可进 7.1，大改排 **7.2.4 Print polish** |
| 物理比例 1:100 | **禁止**本阶段承诺；仅 7.2.4 |

---

## 明确不做

- 不引入 ReportLab / WeasyPrint / Chromium headless / PDF canvas  
- 不把「浏览器里看着没问题」写成 7.1 已关闭  
- 不在未跑本矩阵前开 7.2 主线（PNG 可并行调研，但 7.1 关门仍靠本表）
