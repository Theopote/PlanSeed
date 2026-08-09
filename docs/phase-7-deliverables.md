# Phase 7 — Deliverables / Export

> **状态：⏸ 等待 Phase 6.7.2 Blind Gate**  
> 总览：[roadmap.md](roadmap.md)  
> 前置：[phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md)（严格独立资格）  
> 说明：6.7.1 Holdout 已过门但语料泄漏，**不**据此开工 Phase 7。

## 为什么是 Export，不是高级分析

Design Kernel（0–5.1.1）与 LLM Infrastructure（6.0–6.6）之后，用户已经能：

```text
理解需求 → 生成 → 比较 → 修改 → 评价 → 保存
```

自然下一问：

> 然后呢？我怎么把这个方案带走？

因此 Phase 7 的产品闭环是 **Deliverable Layer**，不是再堆分析轴或再扩 LLM。

## 第一版范围（建议）

**Export Design Report**（最有价值的第一刀）：

| 内容 | 说明 |
|------|------|
| 项目需求 | RequirementSpec 摘要 |
| 平面图 | SVG / PNG |
| 房间面积表 | 自 placements / program |
| 设计评分 | 七轴 `DesignScore` |
| 主要 Findings | `DesignFinding` |
| Assumptions / Unknowns | 会话事实源 |
| Candidate provenance | seed / generator / versions |

格式优先级：

1. PDF（或 HTML→打印成报告）  
2. SVG / PNG  
3. JSON 项目快照  
4. DXF（后续，不挡第一版）

## 明确不做（本阶段）

- Advanced Site / Environmental Analysis  
- Code Profiles  
- Interoperability / BIM  
- 跨平台 packaging 硬化  
- 交互编辑加深  
- 回头重构 solver · 扩 LLM feature  

这些若需要，以后**单独开阶段**；现在不正式规划到 Phase 10，避免「7+ 大杂烩」再次失焦。

## 与 6.7 的边界

```text
6.7 证明 LLM 好用（真模型 + Alpha Gate）
  → Phase 6 ✅ Alpha Qualified
  → 7 做「可以输出成果的设计工具」
```

## Definition of Done（草案）

1. 用户可从当前选中方案导出一份 Design Report  
2. 报告含上表核心块；平面图可读  
3. JSON 快照可再导入或至少可归档  
4. 不引入云端渲染 / 云端 LLM  

（正式开工前再细化为子任务与 API 契约 additive。）
