# AI游戏开发工作室协作入口

## 当前目标与运行范围
项目为 HTML/CSS/JavaScript + Python 中文文字修仙游戏。原v0.1青岚短篇是序章，当前W1实现完整凡界：世界势力、功法境界灵根体质、宗门师徒家族社交、四艺、秘境洞府奇遇、副本Boss、经济拍卖、NPC剧情任务、成就称号榜、规则AI事件和长线赛季。用户明确仅单机NPC模拟：演武/三域赛/拍卖不是实际真人PVP、跨服或玩家互市。仙界仅保留版本扩展，不纳入本版。不得再以序章MVP范围宣布完整凡界完成。

## 开始与恢复
先读 `README.md`、`docs/studio/README.md`、`docs/studio/TASKS.md`、`docs/studio/DECISIONS.md` 和对应岗位文档。当前W1的冻结设计、接口、模型、评审与验收在 `docs/iterations/`，以 `COVERAGE.md`、`WORLD_API.md`、`WORLD_DATA.md`、`WORLD_TESTING.md` 的实际状态/证据为准。原GDD/API及首版报告保留为序章历史，不能当作新功能测试通过。

使用现有检出；任务本已隔离，除用户明确要求外不创建Git worktree。保留玩家数据和现有修改，不能以测试或迁移覆盖真实档。运行标准库Python，不引入外部账号/付费API或未授权费用。

## 团队职责
唯一主Agent担任项目经理，统一维护任务/决策、文件归属、审查和最终验收。五岗位为主策划、技术架构师、视觉与交互设计师、开发工程师、QA与交付工程师；岗位规范见 `docs/studio/roles/`。需要时按文档重新创建/恢复岗位，不依赖旧会话存活，子智能体不得自行扩充团队。

委派包含目标、输入、文件范围、依赖与验收；多人不得同时写同文件。当前实现分工：策划维护world_config内容，开发维护world/rules，架构维护storage/server与模型迁移，视觉维护static，QA维护独立集成/浏览器测试；新增任务由PM重新明确归属。各岗位每次交付报告文件、实际检查、结果、风险及未运行项。

## 质量与数据约束
每轮执行缺口→方案→影响分析→数据/交互→联动检查→实际验证，允许并行独立工作。设计前置、交叉质疑和独立QA不能省略；修复后按影响回归，不删除有效断言或把未运行/跳过当通过。NPC模拟不得伪装真人，所有按钮有实际后端/状态，所有游戏后端能力有可达UI入口。

世界操作沿用request_id与expected_revision、SQLite原子事务。world资产与序章资产隔离，顶层actions_taken/logs是全局历史。保存/载入包含全部单机世界，但revision/请求账本不能回退。schema1须 `--migrate-save` 显式先备份再升级current/slot；损坏或未知schema拒绝保留，禁止静默清档。备份要停服，手动slot不是灾备。

验证入口：`python -m tests.parallel`（并行白盒全量，约30–45秒；可加子串只跑部分）或串行 `python -m unittest discover -s tests -v`、`python -m tests.browser_smoke`、`python -m tests.browser_world`。后两者为可选开发依赖Playwright/系统Chromium；游戏运行无第三方包。测试使用独立临时数据，不对玩家data注入故障。完成状态仅按最新代码和当轮实际证据，不沿用历史通过证明新改动。

## 本轮交付状态
R5自动斗法已接入正式游戏并退役点击式战斗（序章 `auto_battle`、世界 `world_auto_battle`；战力型法宝独立出击/回护；响应带不入存档的 `battle_report` 回放）。规则/接口/限制见 `docs/iterations/R5_INTEGRATION.md`；白盒全量196项通过，真实浏览器套件需Playwright/Chromium、本轮未运行，战力型法宝经济重平衡与存档级战报未做。下文R5为其前序独立实验记录。

此前新增 R5 独立空中斗法评审与实验，统一结论 `docs/iterations/R5_DECISIONS.md`、最新独立验收 `R5_LAB_TESTING.md`、代码 `prototypes/r5-combat/`。PM 维护统一结论/任务/打包；策划维护 R5_DESIGN_PROPOSAL；架构维护 R5_ARCHITECTURE_PROPOSAL；开发维护实验 engine/server/README；视觉维护实验 static 与 R5_UI_PROPOSAL；QA 维护实验 tests、验收证据及 R5_LAB_TESTING。正式 game/static/data 与 v1.2 发行包不能因实验被改写；本轮实验不代表正式自动战斗、持久化迁移和经济重平衡已完成。

R4首周节奏迭代v1.2.0已完成181项全量（790.929s、无失败/跳过）和四套真实浏览器验收，同源源码归档独立解包与CRC/逐文件SHA/运行源一致性亦已通过。当前有效规则见docs/iterations/R4_DESIGN.md、R4_API.md、R4_IMPLEMENTATION.md和docs/R4_PLAYING.md：curve_v2保45基础日但首段0.5/1.5/3日；cadence恢复资格初始3/8h1/容量3；journey七段故事/三精英/手战证明；同章同难一次手胜后正式资格快捷结算。旧schema2长线先唯一备份再一次内容升级，free/schema1不静默切换。不能再以R3每日3次或旧144450总成本作为当前规则。五岗当前归属：策划r3/gameplay_config与设计路线，架构growth/cadence/storage/activities与架构测试，开发world/loot/journey，视觉static，QA其余R4/回归/浏览器，PM文档/版本/打包。最终通过数和源码hash以R4_TESTING实际记录为准。

R3长线版本v1.1.0已实现并验收：136项全量、晚修50项R3/15项架构回归、三个真实浏览器、16新增动作投影和独立解包运行通过，完整边界见docs/iterations/R3_TESTING.md和docs/DELIVERY.md。新Store/HTTP默认longline，旧free兼容；持续修炼、实例掉落/法宝、独立伤害世界Boss，以及主策划主动补充的高难机制/日周活动/目标引导均已落地。此结论不保证未来修改自动通过，不把模拟44.51日当真人观察。角色分工：策划r3_config/gameplay_config，开发loot/world/rules，架构growth/storage/activities与R3_API，视觉static，QA所有r3测试；PM统一版本与归档。

W1凡界版v1.0.0已按22条矩阵完成验收：冻结76项无跳过，两浏览器通过，独立解压运行通过，详COVERAGE/WORLD_TESTING。此为本版定义内容范围的结论，不代表后续扩展或未来改动自动通过。持续迭代按新发现/反馈开新轮次，保留回归和存档兼容，仙界仍单独下一重大版本。
