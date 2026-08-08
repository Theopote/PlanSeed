# Phase 3.5 — Core Consolidation & Local Desktop Runtime

> **← 当前阶段**  
> 停止继续扩展 solver feature。不要开始 Ollama。  
> 收口 Solver → Evaluation → API → Desktop 数据链，并让 PlanSeed 成为**用户无需手动启动 Python**的本地桌面应用。

## 工程工具

```bash
uv run pytest
uv run ruff check packages solver backend
uv run mypy packages solver backend   # 宽松基线，后续收紧
```


## 产品原则（本轮最重要）

1. **UI 只是观察和控制 solver 的窗口。**  
   不要因为四区壳已出现就疯狂加按钮。  
   要做扎实的链：

   ```text
   DesignEvaluation → DesignFinding → Inspector → Candidate Compare
   ```

   同时：**不要用这条原则把「已有 findings 写成人话」无限往后推**——七轴解释是用户判断「有没有判断力」的第一印象。
2. **最大产品缺口是本地独立运行，不是再堆 solver。**  
   任何「请先启动 uvicorn / 手动 Python」文案与目标冲突。  
   Desktop Alpha 里程碑：

   ```text
   双击 PlanSeed
        ↓
   后台自动启动引擎
        ↓
   输入住宅需求 → Generate → Top 5
        ↓
   查看评分与设计解释
        ↓
   A/B 比较
   ```

   该闭环跑通 = **第一个真正可用的 Desktop Alpha**。

---

## 优先级

### P0 — 评价与文档收口

| 项 | 状态 |
|----|------|
| DesignEvaluation / Finding model | ✅（`DesignEvaluation = DesignScore`；`LayoutCandidate.evaluation`） |
| Metric ownership | ✅（`ownership.py`） |
| 删除 API 重复评价 | ✅ |
| roadmap 与代码一致 | ✅（持续维护） |

### P0 — Tauri sidecar runtime（产品定位能否成立）

| 项 | 状态 |
|----|------|
| `pnpm dev` 一键引擎 + UI | ✅ |
| Tauri spawn / kill；**setup 不阻塞**，`engine-ready` 异步通知 | ✅ |
| **PyInstaller `--onedir`** + `bundle.resources`（非 onefile / 非 externalBin） | ✅ 脚本与路径已切 |
| Windows 真装包验收（零系统 Python） | ❌ **仍为关键缺口**（需本机跑 build 脚本 + `tauri:build`） |
| 动态/预留端口；前端 `get_engine_url` | ✅ |
| 端口占用 / 超时 UI 提示 | 🟡 |

### P1

| 项 | 状态 |
|----|------|
| API layering（routes / schemas / services） | ✅ |
| **Inspector findings 人话解释**（七轴「为什么」） | **并行加深**；禁止用「少加按钮」无限推迟 |
| **Candidate Compare（A vs B）** | ✅ MVP（Strip Alt+点击；Inspector 对照表 + 优势差分） |

### P2

| 项 | 状态 |
|----|------|
| Rejected Candidates（为何被淘汰） | ❌ 规划中；先服务 solver 调试，后可对建筑师开放 |
| Local LLM Requirement Parser | ❌ **本阶段不做** |

---

## Candidate Compare（P1 规格）

Top-K 不只是点击切换 A/B/C/D/E。

第一版：**Compare A vs B**

```text
                A       B
Total           89      87
Program         95      95
Spatial         …       …
Circulation     91      76
Privacy         88      94
Environment     92      84
Technical       …       …
Robustness      96      78
```

并解释（**deterministic**，由 score/findings 差分生成，**禁止 LLM**）：

```text
A 的优势
+ 交通更直接
+ 客厅南向
+ 几乎无需 repair

B 的优势
+ 卧室私密性更高
+ 面积分配更紧凑
```

实现落点：四区工作台内加深（Strip 多选 / Inspector 比较模式），**不另起 UI 体系**。

---

## Rejected Candidates（后续）

Inspector / 开发模式可看未进 Top-K 或 invalid 候选：

```text
Seed 47
Rejected because:
• Bedroom 2 unreachable
• Required Kitchen–Dining opening unavailable
• Stair core placement failed
```

价值：solver 可调试；对用户体现「有判断依据，而非随机吐方案」。  
正式产品可隐藏高级 debug 细节。

---

## Definition of Done（Desktop Alpha）

1. roadmap 与真实代码一致  
2. evaluation 不重复执行；candidate 自带完整 `DesignEvaluation`  
3. deterministic DesignFinding 可解释优缺点  
4. metric 不重复计权  
5. Inspector 展示 findings（非空标签）  
6. **A/B Candidate Compare 可用**  
7. backend 分层  
8. **Tauri 自动启动 backend；生产不要求手跑 uvicorn**  
9. backend 生命周期由 Desktop 管理  
10. tests 全通过  

完成后停止扩展；下一阶段再加深交互工作台，然后才是 Local LLM。

---

## 明确不做（本阶段）

Ollama / RAG / fine-tuning / CAD / BIM / 房间拖拽 / 施工图 / 合规引擎 / 推倒四区 UI。

---

## 成熟度快照（自评，2026-08）

| 模块 | 分 |
|------|-----|
| Architecture | 8/10 |
| Schema | 8/10 |
| Geometry | 7/10 |
| Topology | 7/10 |
| Circulation | 6.5/10 |
| Evaluation | 6/10 |
| Explainability | 4/10 |
| Desktop | 3.5/10 |
| Local runtime | 2/10 |
| LLM | 0/10 |

**最大进步：** Topology / Circulation / Architectural evaluation。  
**最大短板：** 已从「solver 不懂住宅」变为「产品各层尚未完全收口」——这是健康变化。
