# Phase 7.1.1-C — Windows WebView2 真实打印验收

> **原则：** CSS / 单元测试 ≠ WebView2 打印一定合理。  
> **Print fallback：** 已优先 `iframe.contentWindow.print()`，禁止 `window.print()` 打主壳。  
> **不做：** 自动截图 diff 系统。现在手测足够。  
> 收口总览：[phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md)

## 环境（固定）

| 项 | 要求 |
|----|------|
| OS | Windows 10 / 11 |
| 壳 | Tauri Desktop |
| 引擎 | WebView2 |
| 打印机 | **Microsoft Print to PDF** |
| 纸张 | A4 · 纵向 |
| 边距 / 缩放 | 系统默认（若改了，记入备注） |

## 生成 8 个打印样本 HTML

```powershell
uv run python scripts/generate_print_smoke_reports.py
```

输出：`debug/print-smoke/`（`P01`…`P08` + `index.html`）。

**第一轮对照：** 可用 Edge 打开同 HTML → Print to PDF（仅参考）。  
**关门：** 必须在 Desktop 报告预览里点 Print → Microsoft Print to PDF。

建议 PDF 命名：`7.1.1-C-P0x-{pass|fail}.pdf`。

---

## 样本矩阵（仅此 8 个）

| ID | 场景 | 文件 | 手测重点 |
|----|------|------|----------|
| **P01** | 单层 / 少房间 | `P01_single_floor.html` | 封面、单平面独页、无多余空白 |
| **P02** | 两层 / 正常住宅 | `P02_two_floor.html` | 层间分页、目录、面积表 |
| **P03** | 三层 | `P03_three_floor.html` | 每层独页、末页不空白失控 |
| **P04** | 超长项目名 | `P04_long_title.html` | 封面标题是否截断 |
| **P05** | 房间较多 | `P05_many_rooms.html` | 面积表跨页 |
| **P06** | Findings 很多 | `P06_many_findings.html` | 长 Findings 是否溢出 |
| **P07** | Blocking Unknown | `P07_blocking_unknown.html` | Cover banner、不打碎平面 |
| **P08** | en-US | `P08_locale_en.html` | 英文字体、北针文案 |

---

## 每份 PDF 必查

| # | 检查点 | Pass? | 备注 |
|---|--------|-------|------|
| 1 | **封面**不被截断 | ☐ | |
| 2 | **目录**合理 | ☐ | |
| 3 | **SVG** 不被跨页切开 | ☐ | |
| 4 | **每层平面独页** | ☐ | P01 单层亦适用 |
| 5 | **表格跨页**可接受（至少不切字） | ☐ | 尤其 P05 |
| 6 | **长 Findings** 不溢出裁切 | ☐ | 尤其 P06 |
| 7 | **中文字体**正常（不方框） | ☐ | P01–P07 |
| 8 | **英文字体**正常 | ☐ | 尤其 P08 |
| 9 | **页边距**合理 | ☐ | |
| 10 | **北针**正确（已知旋转 / 未知不画假 ↑N） | ☐ | |
| 11 | **面积表**可读 | ☐ | |
| 12 | **页脚 / Provenance** 不乱 | ☐ | |

场景总评：`Pass` / `Fail` / `Pass-with-notes`

---

## 结果记录（人手填）

| ID | 总评 | 失败项 (#) | 日期 | 操作者 | 备注 |
|----|------|------------|------|--------|------|
| P01 | | | | | |
| P02 | | | | | |
| P03 | | | | | |
| P04 | | | | | |
| P05 | | | | | |
| P06 | | | | | |
| P07 | | | | | |
| P08 | | | | | |

**环境确认：** Windows __ · WebView2 Print · Microsoft Print to PDF · A4 纵向

---

## 关门条件（7.1.1-C）

- [ ] 上表 8 行均有 Desktop 实测记录  
- [ ] 无 **P0**：主壳被打印 · SVG 拦腰切断 · 中文全面方框 · blocking banner 不可见  
- [ ] P1（空白页、表跨页丑）记「已知限制」→ 可进 **7.2.4 Print polish**，不挡 7.2.1 SVG  
- [ ] **禁止**用截图 diff / headless Chromium 代替本表  

填完后勾 [phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md) DoD 第 3 条 → 开工 **7.2.1**。
