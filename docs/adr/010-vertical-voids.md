# ADR-010 — Vertical Voids: 统一 Stair Core / Atrium / Wet Riser

## Status

**Proposed**（非 Accepted）。待 v0.1.x 观察窗口结束、正式开下一阶段时再决定是否 Accept。
本 ADR 与配套 [proposals/vertical-systems.md](../proposals/vertical-systems.md) 均为设计存档，**不代表已排期**。

## Context

现状核对（均已用当前代码 + benchmark_program 实测，非推测）：

1. **StairCore 是目前唯一的"跨层锁位"几何**：`solver/circulation/stair_core.py` 计算一个
   `CorePlacementResult`，`guillotine.py` 里注释明确写着"跨层共享 free：只扣 StairCore（房间/
   分区锁不得投影到其它层）"——也就是说，除了楼梯，**没有任何机制支持"某几层共享同一个不可
   建区域"**，天井/采光井目前完全不存在于 schema 里。

2. **湿区跨层对齐已有 evaluation，但通过门槛极低、且是软约束**：
   `solver/evaluation/vertical.py::wet_alignment_from_geometry` 计算的是**每层湿区房间外包盒
   （AABB）之间的 IoU**，`checker_impl.py::_check_wet_stack_alignment` 的判定是
   `score > 1e-6` 即视为通过（`ConstraintEvaluationResult.empty()`），且即使触发违规也是
   `hard=False`。实测 benchmark_program 在 candidate_count=64 时的 Top-5，
   `wet_alignment_IoU` 分布在 **0.135–0.273**，远低于"两层湿区实际能共用立管"应有的重叠度，
   但因为门槛只要 `>1e-6` 就全部判定通过。个别房间对（如 seed=48 的 r3 与 r9）在 y 方向
   完全不重叠，仍然被判定"已对齐"。

3. `RoomSpec.daylight_required` 字段已存在，但目前只影响朝向评分（Environment 轴），
   没有任何几何后果——不会真的在图上开天井或窗，语义和实现之间有落差。

这三点合在一起，正是最近一轮"平面质量检查"里发现的 gap/超面积问题的同一个根：**当前架构里
唯一被当作"一等公民"处理的竖向元素只有楼梯**，天井（纯留白）和管井（房间位置强对齐）这两类
同样重要的竖向约束，要么完全不存在，要么存在但强度不足以真正起作用。

## Decision

1. 新增 `VerticalVoidSpec`（`packages/schema/vertical_void.py`），泛化现有 `CorePlacement` /
   `StairCoreSpec`：

   ```python
   class VerticalVoidType(StrEnum):
       STAIR = "stair"
       ATRIUM = "atrium"
       WET_RISER = "wet_riser"

   class VerticalVoidSpec(BaseModel):
       id: str
       void_type: VerticalVoidType
       floor_span: tuple[str, str]        # (起始 FloorSpec.id, 终止 FloorSpec.id)，按声明顺序取连续区间
       width: float | None = None          # STAIR 缺省复用 StairCoreSpec 默认；ATRIUM 需显式
       depth: float | None = None
       preferred_placement: CorePlacement | None = None
       skylight_required: bool = False     # 仅 ATRIUM：顶层是否需天窗，供 evaluation/export 标注
       alignment_tolerance: float = 0.3    # 仅 WET_RISER：允许的 footprint 偏移容差（米）
   ```

2. **STAIR / ATRIUM 走同一条几何路径**：两者都是"预先从 free space 里扣除的固定矩形，按
   `floor_span` 过滤是否作用于当前层"，直接泛化 `guillotine.py` 里现有的
   `subtract_rects([floor_rect], [core_rect])` 调用，从"固定扣一个 core_rect"改成
   "扣除所有 `floor_span` 覆盖当前楼层的 void 列表"。**STAIR 的 `floor_span` 恒等于全部楼层**
   （不开放用户配置为部分楼层——楼梯必须每层可达，这是硬性事实，不是设计偏好）；
   **ATRIUM 的 `floor_span` 用户可配置为任意连续 ≥2 层区间**（对应你说的"贯通全部/只连底部
   两层/只连顶部两层"三种取舍，不在算法里预设哪种更好）。

3. **WET_RISER 不走"预先扣除"路径**，这是和 STAIR/ATRIUM 本质不同的地方，不能强行用同一套
   机制，需要老实分两步做：

   - **Step A（低成本，先做）**：把 `_check_wet_stack_alignment` 的判定从
     "`score > 1e-6` 即通过、且 `hard=False`"，升级为"**每一对相邻楼层的湿区房间，按
     `semantic_role`/`tags` 配对后逐对计算 IoU，最低值须 ≥ 阈值（默认 0.6，可通过
     `alignment_tolerance` 反推），未达标 `hard=True` 直接拒绝候选**"。这一步复用现有
     candidate 生成 + 拒绝流程，做法和最近修复"房间面积超限"完全同构（不改生成器内部逻辑，
     只是让筛选环节真正卡住不合格的候选），成本低、见效快，但会显著提高候选被拒率，
     需要同步评估是否要提高默认 `candidate_count`。
   - **Step B（后续再做，成本更高）**：Step A 只能"筛掉不好的"，筛不出"更好的"——如果
     benchmark 类房型湿区权重本来就分散在两层不同位置，Step A 可能导致大量候选被拒到
     没有合法方案。真正的修复是让生成器在放置湿区房间时**参考一个"湿区锚点矩形"**
     （由湿区面积需求最大的楼层先行布局决定），后续楼层的湿区房间生成时优先尝试落入
     该锚点矩形，退化时才允许偏移——这需要改 `guillotine.py` 内部的房间分配顺序，
     不是单纯加一道拒绝检查，工作量明显大于 Step A，建议先上 Step A 观察实际拒绝率，
     再决定要不要投入 Step B。

## Consequences

- STAIR 的 `floor_span` 强制为全部楼层，是本 ADR 唯一"不给用户开放"的参数，明确写在这里
  避免后续被误当作遗漏。
- ATRIUM 上线后，一部分楼层会出现"合法的空白区域"——这和最近刚修复的"非法空白区域"
  （问题1）在几何上长得一样，**必须在校验逻辑里能区分两者**：合法空白必须能追溯到某个
  `VerticalVoidSpec(void_type=ATRIUM)`，否则仍按问题1的规则判定为缺陷。这是本提案里最容易
  和近期修复冲突回归的地方，实现时两边测试要交叉跑。
- Step A 上线预计会提高候选拒绝率（参考近期面积约束上线后 `valid` 从 64→34 的量级），
  需要重新评估 `candidate_count` 默认值，并追加类似 `test_area_constraints.py` 的批量
  seed 回归测试。
- 本提案**不**声称做到真实给排水施工图深度（管径、坡度、检修井、通气帽出屋面位置等）——
  和 ADR-009 对 Shapely 的表态一致，这里只解决"房间几何位置是否为立管贯通留出了可能性"，
  仍然是 heuristic-only，不构成规范符合性声明，需要在对应 DesignFinding 里注明。
- 三者共用 `VerticalVoidSpec` 只是**数据模型和"跨层位置约束"这个概念**上的统一，
  不代表三者用同一套放置算法——STAIR/ATRIUM 是"预扣除"，WET_RISER 是"事后/联合约束"，
  文档和代码注释都要把这个区别写清楚，避免后来者以为三者可以无脑套同一个 placement 函数。
