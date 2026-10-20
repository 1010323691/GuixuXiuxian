# AI 游戏开发工作室

## 当前阶段
正式交付版本为 R4 v1.2.0，运行与交付证据见 `docs/iterations/R4_TESTING.md`。当前 R5 是独立空中自动斗法实验与设计评审：统一裁决 `docs/iterations/R5_DECISIONS.md`，实测状态 `R5_LAB_TESTING.md`，代码/启动 `prototypes/r5-combat/README.md`。五岗已围绕神识灵印代身、独立双法宝、CD、预算和正式接入进行多轮交叉评审；实验不连接正式存档或奖励，不能视为正式战斗已替换。下文 R3/W1 保留为阶段历史。

R3长线v1.1.0已完成应用实现、独立回归、真实浏览器和解压运行验收，证据见最新R3_TESTING与DELIVERY。范围包括持续修炼、实例装备/双法宝、章节难度掉落、独立伤害世界Boss、小境界和主策划主动补充的高难机制/日周活动/真实目标引导。恢复工作先读TASKS.md的R3段与下方R3文档，不以旧W1通过证明新版本。

W1完整凡界已实现，冻结版本76项及两套浏览器已通过，独立运行归档验收通过，最终凡界v1.0.0交付包及校验清单已生成。原短篇保留为序章。用户明确NPC单机模拟，无真实联网PVP/跨服；仙界只预留扩展。最终状态以docs/iterations/COVERAGE.md、WORLD_TESTING.md及TASKS.md为准，不以旧v0.1结论代替W1。

## 团队与调度
项目经理是唯一主 Agent，负责需求、任务分配、依赖、审查与最终验收。五个专业角色见 roles/。角色只修改分配的文件；跨模块变更先由项目经理协调。子智能体不得自行扩充团队。

## 恢复与交接
每次开始先阅读本文件、TASKS.md、DECISIONS.md 及对应岗位文档。Agent 会话不是持久化配置；新会话由项目经理按角色文档重新创建并分配任务。

每项任务记录目标、负责人、输入、允许修改范围、依赖、验收标准、状态及验证证据。交付必须包含结果、修改文件、实际执行的测试及剩余问题。未执行验证不能记作通过。

## 协作流程
用户需求 → 策划定义规则和验收 → 架构明确模块与接口 → 开发及美术按文件范围并行 → QA 独立验证 → 缺陷修复与回归 → 构建交付 → 项目经理验收。

普通实现决策自主推进。核心定位变更、未授权费用、重大破坏性操作或无法协调的需求冲突须由用户决定。禁止为通过测试删除有效测试或绕过验证。

## 文档索引
- TASKS.md：里程碑与任务状态
- DECISIONS.md：关键决策与待定事项
- roles/：岗位职责、输入输出、交接与维护要求

正式需求到达后，再建立 GDD、技术方案、资源规范、测试计划等实际项目文档，避免提前将假设写成需求。

## 首版恢复索引
先读项目根 README.md；冻结规则 docs/GDD.md、技术 docs/ARCHITECTURE.md、接口 docs/API.md、界面 docs/UI.md、测试 docs/TESTING.md、平衡 docs/BALANCE.md、架构审查 docs/REVIEW.md。所有相对 docs/ 路径均以仓库根目录为基准。后续扩展须保持现有存档和完整通关回归。

## W1权威文档
所有路径以仓库根为准：docs/iterations/WORLD_DESIGN.md（精确内容及多轮裁决）、WORLD_API.md（权威交互协议）、WORLD_DATA.md（实际数据模型）、WORLD_ARCHITECTURE.md（迁移与架构证据）、WORLD_UI.md（真实界面）、WORLD_BALANCE.md（两独立路线）、WORLD_REVIEW.md（问题与修复）、COVERAGE.md（逐模块门槛）、WORLD_TESTING.md（QA实际执行）。新读者先看README.md和docs/PLAYING.md。

## R3恢复索引
长线玩法见docs/R3_PLAYING.md；实际契约docs/iterations/R3_API.md；配表/策划验收R3_IMPLEMENTATION.md；主动全系统审查与取舍R3_GAMEPLAY_REVIEW.md；开发与性能R3_DEV_IMPLEMENTATION.md；界面与真实页面证据R3_UI.md；最终独立测试R3_TESTING.md。MONTH_BALANCE_*保留设计与40场景积分来源，不能代替实际掉落、通关和UI证据。各岗位仍按文件归属协作，应用冻结后仅修明确缺陷并记录哈希/影响/重验。

## 当前R4迭代
用户已授权首周更快/多次回流/后期减负实际落地，当前版本目标v1.2.0。统一规则R4_DESIGN、R4_API、R4_IMPLEMENTATION、R4_UI与独立R4_TESTING位于docs/iterations；玩家手册docs/R4_PLAYING.md。任务总表与决策记录已持久化。R3的每日额度与旧阶段成本保留为历史，不能覆盖本轮冻结契约。181项全量与四套真实浏览器已通过，完整月余与当前章三难独立路线有证据；正式归档独立解包验收亦通过，实际结果见DELIVERY及包外package-smoke/manifest。
