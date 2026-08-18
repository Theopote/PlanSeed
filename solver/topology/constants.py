"""拓扑 / 通行共享常量 — 避免 access ↔ doors ↔ derive 循环导入。"""

ENTRY_NODE_ID = "exterior-entry"
MIN_ACCESS_WALL = 0.9  # 开口共边门槛（米）；≠ 自动 PASSAGE
MIN_MEANINGFUL_CORRIDOR_SHORT = MIN_ACCESS_WALL * 1.5  # 走廊碎片最短边下限
MIN_CORRIDOR_SLIVER_SHORT = 0.5  # 狭长残余碎片另一维下限
