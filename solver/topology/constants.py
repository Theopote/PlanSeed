"""拓扑 / 通行共享常量 — 避免 access ↔ doors ↔ derive 循环导入。"""

ENTRY_NODE_ID = "exterior-entry"
MIN_ACCESS_WALL = 0.9  # 开口共边门槛（米）；≠ 自动 PASSAGE
