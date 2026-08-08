/** 七轴显示名与范围说明（轴标识冻结；文案限定 MVP 范围，避免过度承诺）。 */

export const AXIS_SCOPE = {
  environment: {
    label: "Environment (Orientation MVP)",
    shortLabel: "Environment",
    categoryZh: "环境·朝向 MVP",
    hint: "当前主要基于朝向与外墙关系，不含日照 / 通风 / 景观模拟",
    compareReason: "朝向与外墙关系更优（Orientation MVP）",
  },
  technical: {
    label: "Technical Logic",
    shortLabel: "Technical",
    categoryZh: "技术逻辑",
    hint: "当前仅包括楼梯、湿区叠置、入口与场地关系；不含结构 / 设备 / 消防 / 法规",
    compareReason: "楼梯 / 湿区 / 入口与场地关系更稳（Technical Logic）",
  },
} as const;
