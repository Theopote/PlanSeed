# 安全策略

## 支持范围

PlanSeed 为早期 Alpha。当前仅对仓库默认分支（`master`）上的最新代码接受安全相关反馈。

## 报告方式

请**不要**在公开 Issue 中贴出可利用细节。

优先通过 GitHub 的 [Private vulnerability reporting](https://github.com/Theopote/PlanSeed/security/advisories/new) 提交；若不可用，可向仓库维护者私信说明：

- 影响版本 / commit
- 复现步骤
- 潜在影响（本地数据、进程、网络等）

我们会尽快确认并协调修复与披露时机。

## 范围说明

- PlanSeed 默认 **local-first**：不依赖云端 LLM API。
- 本地 sidecar / FastAPI 默认绑定本机；若自行暴露到局域网或公网，请自行评估风险。
- 请勿将 API key、模型路径中的隐私、或用户项目数据提交到本仓库。
