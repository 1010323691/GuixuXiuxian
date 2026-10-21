# AI 游戏开发工作室

## 当前阶段
当前主线为**多用户在线化（MU）**：服务化多账号、单库 `data/game.db` 按 `user_id` 隔离、服务端自动保存。需求 `docs/iterations/MU_PRD.md`，设计 `MU_DESIGN.md`（v2，方案B）与两张 mermaid 图，交接 `MU_HANDOFF.md`，现行接口 `docs/API.md`，任务与决策见 `TASKS.md`、`DECISIONS.md` 的MU条目。其测试、浏览器套件与部署实测以 QA 记录为准，未验证项不得写成已通过。

**历史文档说明**：本目录与 `docs/history/`、`docs/iterations/`（本轮 MU_* 除外）、`docs/studio/proposals/`、`artifacts/`、`prototypes/` 中出现的“存档/载入/检查点/单机”等描述，对应的是v1.2及更早的单机行为，现行行为以 MU_DESIGN、`docs/API.md` 与根目录 README 为准；历史文档保留原文，不改写。

正式交付版本为 R4 v1.2.0（多用户化之前），运行与交付证据见 `docs/iterations/R4_TESTING.md`。R5 自动斗法已接入正式游戏（`docs/iterations/R5_INTEGRATION.md`），独立实验见 `docs/iterations/R5_DECISIONS.md`、`R5_LAB_TESTING.md` 与 `prototypes/r5-combat/README.md`。下文 R3/W1 保留为阶段历史。

R3长线v1.1.0已完成应用实现、独立回归、真实浏览器和解压运行验收，证据见最新R3_TESTING与DELIVERY。范围包括持续修炼、实例装备/双法宝、章节难度掉落、独立伤害世界Boss、小境界和主策划主动补充的高难机制/日周活动/真实目标引导。恢复工作先读TASKS.md的R3段与下方R3文档，不以旧W1通过证明新版本。

W1完整凡界已实现，冻结版本76项及两套浏览器已通过，独立运行归档验收通过，最终凡界v1.0.0交付包及校验清单已生成。原短篇保留为序章。用户明确所有社交与竞技为NPC模拟，无真实联网PVP/跨服（多用户化后账号之间亦无互动）；仙界只预留扩展。最终状态以docs/iterations/COVERAGE.md、WORLD_TESTING.md及TASKS.md为准，不以旧v0.1结论代替W1。

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
先读项目根 README.md；冻结规则 docs/GDD.md、技术 docs/ARCHITECTURE.md、接口 docs/API.md（现行多用户契约）、界面 docs/UI.md、测试 docs/TESTING.md、平衡 docs/BALANCE.md、架构审查 docs/REVIEW.md。所有相对 docs/ 路径均以仓库根目录为基准。后续扩展须保持现有进度数据兼容和完整通关回归。

## W1权威文档
所有路径以仓库根为准：docs/iterations/WORLD_DESIGN.md（精确内容及多轮裁决）、WORLD_API.md（权威交互协议）、WORLD_DATA.md（实际数据模型）、WORLD_ARCHITECTURE.md（迁移与架构证据）、WORLD_UI.md（真实界面）、WORLD_BALANCE.md（两独立路线）、WORLD_REVIEW.md（问题与修复）、COVERAGE.md（逐模块门槛）、WORLD_TESTING.md（QA实际执行）。新读者先看README.md和docs/PLAYING.md。

## R3恢复索引
长线玩法见docs/R3_PLAYING.md；实际契约docs/iterations/R3_API.md；配表/策划验收R3_IMPLEMENTATION.md；主动全系统审查与取舍R3_GAMEPLAY_REVIEW.md；开发与性能R3_DEV_IMPLEMENTATION.md；界面与真实页面证据R3_UI.md；最终独立测试R3_TESTING.md。MONTH_BALANCE_*保留设计与40场景积分来源，不能代替实际掉落、通关和UI证据。各岗位仍按文件归属协作，应用冻结后仅修明确缺陷并记录哈希/影响/重验。

## 当前R4迭代
用户已授权首周更快/多次回流/后期减负实际落地，当前版本目标v1.2.0。统一规则R4_DESIGN、R4_API、R4_IMPLEMENTATION、R4_UI与独立R4_TESTING位于docs/iterations；玩家手册docs/R4_PLAYING.md。任务总表与决策记录已持久化。R3的每日额度与旧阶段成本保留为历史，不能覆盖本轮冻结契约。181项全量与四套真实浏览器已通过，完整月余与当前章三难独立路线有证据；正式归档独立解包验收亦通过，实际结果见DELIVERY及包外package-smoke/manifest。

## MU 多用户在线化恢复索引
先读 `docs/iterations/MU_PRD.md`（21条AC与默认值）、`MU_DESIGN.md`（方案B：单库+`user_id`+WAL、短事务乐观提交、迁移与认领、改造清单与处置表）、`MU_HANDOFF.md`（方案A→B 交接与环境问题），再读 `docs/API.md` 与根目录 README 的部署与运维一节。任务拆分 T01 存储与迁移、T02 认证与服务入口、T03 文案服务化、T04 前端、T05 测试脚本文档，文件归属互不重叠。派工须显式指定可用子代理模型；浏览器套件依赖本机 Playwright，不可用须记“未运行”。
