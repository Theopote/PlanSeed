# Phase 5 — Project Persistence & Variant Lineage

> **状态：P0 血缘 + P1 SQLite 快照已落地。**  
> 总览：[roadmap.md](roadmap.md)

## 目标

1. **Variant 血缘**：Create Variant 可解释父子与代数（设计过程树）。  
2. **本地持久化**：SQLite 保存/打开整项目快照（program + locks + candidates）。  
3. **重开可解释**：区分「布局几何按快照」与「evaluation_version 已变、分数可能不可比」。

## 血缘字段（additive）

| 字段 | 含义 |
|------|------|
| `variant_parent_id` | Create Variant 时的父候选 id；根为 `null` |
| `variant_generation` | 相对根代数：0=根，1=A·1，2=A·2… |
| `lock_snapshot_id` | 生成时 `LayoutLocks` 指纹（16 hex） |

写入路径：

- 首次 Generate / Benchmark：`parent=null`, `generation=0`, `lock_snapshot_id=fingerprint(locks)`  
- Create Variant：每个新候选 `parent=选中候选`, `generation=parent+1`, 当前 locks 指纹  
- Regenerate unlocked：仍为新根（generation=0），带当前锁指纹  

Strip 展示：`A` / `A·1`（见 `lineage_label`）；悬停可见父 id 与锁指纹。

### locks 指纹

```text
LayoutLocks → model_dump / 等价 JSON → sort_keys → sha256 → 前 16 hex
```

实现：`packages/schema/lineage.py::locks_fingerprint`；桌面镜像 `desktop/src/lib/lineage.ts`。

## SQLite 项目快照

- 默认路径：`~/.planseed/projects.db`  
- 覆盖：环境变量 `PLANSEED_DB`  
- 表：`projects(id, name, updated_at, payload_json)`  
- **Schema 版本**：`PRAGMA user_version`；打开时 `migrate(conn)`（Phase 7.5-C，见 [phase-7.5-alpha-hardening.md](phase-7.5-alpha-hardening.md)） 

`payload` 形状：

```text
{
  form, program, locks, candidates,
  selected_id, compare_id?,
  schema_versions: { solver_version, generator_version, evaluation_version }
}
```

### API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 列表 |
| POST | `/api/projects` | 创建/更新（body: name, id?, payload） |
| GET | `/api/projects/{id}` | 详情；带 `evaluation_version_mismatch` |
| DELETE | `/api/projects/{id}` | 删除 |
| GET | `/api/projects/{id}/package` | Phase 7.5-D：导出 `.planseed` ZIP |
| POST | `/api/projects/import` | Phase 7.5-D：导入 ZIP（按包内 id upsert） |

`.planseed` 布局：`manifest.json` + `project.json` + `assets/` + `previews/`（见 [phase-7.5-alpha-hardening.md](phase-7.5-alpha-hardening.md)）。

保存时服务端写入 `project_meta`（format/app），并**保留**快照内设计 `schema_versions`（不得仅因 Save 升为 current）。打开时若快照 `evaluation_version` ≠ 当前常量 → UI 提示分数不可比、几何仍有效。详见 [phase-5.1-revision-integrity.md](phase-5.1-revision-integrity.md)。

## 明确不做

- 云同步 / 多用户  
- 文件选择器复杂 UX（本轮为应用内项目列表）  
- Packaging / CSP / macOS（**非** Phase 7 Export；另阶段）  
- LLM

## Definition of Done

1. Create Variant 后 Strip 可见代数与父提示  
2. 同锁同指纹（Python 测）  
3. Save → Open 恢复候选树、锁、选中项  
4. 旧 evaluation_version 快照触发 mismatch 提示  
5. 现有 generate / lock / mutation 回归仍绿
