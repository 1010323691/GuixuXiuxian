# AI游戏开发工作室协作入口

## 当前目标与运行范围
项目为 HTML/CSS/JavaScript + Python 中文文字修仙游戏，现为**服务化多用户在线游戏**：玩家注册/登录账号，各账号进度以 `user_id` 隔离，同一服务进程、同一个 `data/game.db` 承载所有账号。原v0.1青岚短篇是序章，当前W1实现完整凡界：世界势力、功法境界灵根体质、宗门师徒家族社交、四艺、秘境洞府奇遇、副本Boss、经济拍卖、NPC剧情任务、成就称号榜、规则AI事件和长线赛季。用户明确所有社交/竞技/拍卖仍是NPC模拟：演武/三域赛/拍卖不是实际真人PVP、跨服或玩家互市；多账号只彼此隔离，账号之间没有任何互动。仙界仅保留版本扩展，不纳入本版。不得再以序章MVP范围宣布完整凡界完成。

## 开始与恢复
先读 `README.md`、`docs/studio/README.md`、`docs/studio/TASKS.md`、`docs/studio/DECISIONS.md` 和对应岗位文档。当前W1的冻结设计、接口、模型、评审与验收在 `docs/iterations/`，以 `COVERAGE.md`、`WORLD_API.md`、`WORLD_DATA.md`、`WORLD_TESTING.md` 的实际状态/证据为准。多用户在线化（MU）的需求、设计与交接在 `docs/iterations/MU_PRD.md`、`MU_DESIGN.md`（v2，方案B）、`MU_HANDOFF.md`，当前接口契约在 `docs/API.md`。原GDD/API及首版报告保留为序章历史，历史文档中的“存档/载入”描述的是v1.2的单机行为，不是现行行为，也不能当作新功能测试通过。

使用现有检出；任务本已隔离，除用户明确要求外不创建Git worktree。保留玩家数据和现有修改，不能以测试或迁移覆盖真实玩家数据。后端运行标准库Python，不引入外部账号/付费API或未授权费用。前端允许内置固定版本的第三方库（现为 `static/vendor/three.module.min.js`，Three.js r170，MIT；斗法台 bundle `static/arena3d.js` 内打包 three.quarks（MIT）与 postprocessing（Zlib），见D015；用户2026-10-21明确裁决取消“不引入第三方包、无外部资源”约束）；库文件只能同源内置，不得改用CDN，且必须有无WebGL的降级路径。

## 团队职责
唯一主Agent担任项目经理，统一维护任务/决策、文件归属、审查和最终验收。五岗位为主策划、技术架构师、视觉与交互设计师、开发工程师、QA与交付工程师；岗位规范见 `docs/studio/roles/`。需要时按文档重新创建/恢复岗位，不依赖旧会话存活，子智能体不得自行扩充团队。

委派包含目标、输入、文件范围、依赖与验收；多人不得同时写同文件。当前实现分工：策划维护world_config内容，开发维护world/rules，架构维护storage/auth/server与模型迁移，视觉维护static，QA维护独立集成/浏览器测试；新增任务由PM重新明确归属。各岗位每次交付报告文件、实际检查、结果、风险及未运行项。

## 质量与数据约束
每轮执行缺口→方案→影响分析→数据/交互→联动检查→实际验证，允许并行独立工作。设计前置、交叉质疑和独立QA不能省略；修复后按影响回归，不删除有效断言或把未运行/跳过当通过。NPC模拟不得伪装真人，所有按钮有实际后端/状态，所有游戏后端能力有可达UI入口（含注册、登录、退出、改密）。

**多账号与自动同步（现行规则）**
- 身份与隔离：账号身份只来自服务端会话Cookie，请求体/URL里没有任何用户参数。进度表 `current`、`requests` 以 `user_id` 隔离（`requests` 主键 `(user_id, request_id)`），所有进度SQL只允许出现在 `game/storage.py` 的唯一数据访问层并必须带 `user_id` 谓词；不得为了便利绕过该层或让某账号读写他人数据。
- 自动保存：没有手动存档/载入，`/api/save`、`/api/load` 已退役为404。每次写操作由服务端在事务提交后才返回成功；提交失败整次回滚并返回503，界面显示“进度保存失败…当前操作未生效”，不得显示已同步。进度库使用WAL与 `synchronous=FULL`，写事务只做乐观版本校验+更新+登记请求，规则计算在事务外。
- 世界操作沿用request_id与expected_revision、SQLite原子事务；同账号并发以版本校验裁决，冲突返回409，不丢更新。world资产与序章资产隔离，顶层actions_taken/logs是账号内的全局历史。revision/请求账本不能回退。
- 数据兼容：旧单机库（`data/game.db` 仍为旧格式）会被服务拒绝启动。须**停服**后运行 `python server.py --migrate-multiuser`（schema1须同时加 `--migrate-save`，显式先备份再迁移），旧进度进入“待认领区”，再由运维 `--claim-legacy 用户名` 认领给已存在的账号；严禁首位注册者自动继承，任何网络路径都读不到待认领区。损坏或未知schema拒绝保留，禁止静默清档。
- 备份：`python server.py --backup` 对单个 `data/game.db` 做WAL在线备份（可不停服，产物在 `data/backups/`），是整库备份，不能按用户单独恢复；不要手拷运行中的 `game.db`（会漏WAL内容）。WAL要求本机文件系统，不支持网络盘。
- 部署：默认只监听本机。对外开放须配 `--allowed-host`，开放注册并面向公网**必须**放在HTTPS反向代理之后并加 `--secure-cookies`（可选 `--trust-proxy`、`--no-register`）。详见 `README.md`。
- 玩家可见文案术语：进度/进度已同步/登录后恢复进度；不在界面、API message、事件日志、启动脚本输出与现行文档中使用“存档、读档、载入、检查点、保存位置、单机”等旧词（历史文档除外），由 `tests/test_terminology.py` 扫描兜底。

验证入口：`python -m tests.parallel`（并行白盒全量，约30–45秒；可加子串只跑部分）或串行 `python -m unittest discover -s tests -v`、`python -m tests.browser_smoke`、`python -m tests.browser_world`。后两者为可选开发依赖Playwright/系统Chromium；后端运行无第三方包。测试使用独立临时数据，不对玩家data注入故障。完成状态仅按最新代码和当轮实际证据，不沿用历史通过证明新改动。

## 本轮交付状态
**云海御空 v2 阶段一（2026-10-21，分支 feat/flight-battle-v2）**：新斗法台源码改为 TypeScript（`src/battle/`，`npm run build` 生成并提交 `static/arena3d.js`；运行无需 Node，`tests/test_frontend_build.py` 校验 bundle 与源码一致），单体战斗实验场 `/battle-lab.html` 已通过用户视觉验收。**阶段二**（D019）：游戏内战报回放已改由新斗法台（`src/battle/replay.ts`）按 `battle_report` 精确同步演出，旧 `battle3d.js` 与 `static/vendor/addons/` 已退役；真实战报回放用 `python -m tests.browser_fx3d_real` 验收，2026-10-21 用户视觉验收通过；回放下方的文字战报已按用户裁决退役（D020），场景与过程保留。**阶段三**（D021，`docs/iterations/FB3_SWARM.md`）：长线进度的凡界战斗有规则层真实小怪（首领败亡即胜、群攻、前瞻选目标），平衡用 `python scripts/swarm_balance.py --check`，斗法台与 SVG 降级都演群战，待用户视觉验收。决策 D015–D019，任务 FB1–FB4，说明见 `docs/visual-effects-plan.md` 末节。
**三维斗法台（2026-10-21，分支 feat/3d-battle-arena）**：战报回放升级为透视三维「云海御空」（当时为 `static/battle3d.js`，已被 v2 阶段二取代），设计与限制见 `docs/visual-effects-plan.md`；证据与未验证项见 `docs/acceptance-report.md` 的对应小节。
**体验重构（2026-10-21，分支 feat/three-battle-fx）**：已新增Three.js统一特效管理器（战报特效、舞台氛围、洞府灯笼）、世界视图 `guide`/`estate` 字段、三处破坏性确认，并修复四套浏览器套件（现可在本机Edge运行，`GUIXU_BROWSER` 可指定浏览器）。证据：白盒392项、五套浏览器套件、44组页面审计，详 `docs/acceptance-report.md`；真实GPU帧率与小时级内存未测。
**多用户在线化（MU，本轮）**：需求 `MU_PRD.md`（21条AC）、设计 `MU_DESIGN.md` v2。隔离方案经用户决策由方案A（每用户一库）改为方案B（单库 `data/game.db` + `user_id` + WAL）。任务拆分T01存储与迁移、T02认证与服务入口、T03文案服务化（已完成，仅改字符串）、T04前端（登录/账号/同步状态）、T05测试/脚本/文档。文档车道（T05-docs）已把 README、`docs/API.md`、本文件与 `docs/studio/` 同步到新架构。**下列项一律以QA实测记录为准，当前未验证的不得写成已通过**：白盒全量（`python -m tests.parallel`）通过数；浏览器套件（Playwright，本机未必可用，未运行即记“未运行”）；scrypt（`n=2^15,r=8,p=1`）在目标机上的耗时；HTTPS反向代理下的 `--secure-cookies`/`--trust-proxy` 实际表现；`synchronous=FULL` 下写事务的P99；`--migrate-multiuser`/`--claim-legacy` 在真实旧库上的演练。用户待确认默认值见 `docs/studio/DECISIONS.md` 的MU条目。

V4设计系统「青绿金碧」已落地正式static：两层token、统一组件与五态按钮、类别字牌事项卡、服务信息的特效（境界灵气、收益飞入、执行金光、损失残影等），一屏不滚动不变。规范与实测见 `docs/iterations/V4_DESIGN_SYSTEM.md`；白盒197项通过、10视口一屏巡检0问题，Playwright浏览器套件本机未运行。（此为MU之前的结论，不代表多用户改动后的状态。）

序章改动：吐纳修为由服务端按时间自动累积（每5秒+1，到境界瓶颈即止，离线不囤积；`cultivate`点击退役），序章分类标签改为「修炼/探索/地区/首领/买卖」；测试用 `tests/support.py` 的 `pass_time`/`TestClock` 拨快时钟，详见 `tests/test_prologue_qi.py`；白盒202项通过，Playwright未运行。

R5自动斗法已接入正式游戏并退役点击式战斗（序章 `auto_battle`、世界 `world_auto_battle`；战力型法宝独立出击/回护；响应带不入库的 `battle_report` 回放）。规则/接口/限制见 `docs/iterations/R5_INTEGRATION.md`；白盒全量196项通过，真实浏览器套件需Playwright/Chromium、本轮未运行，战力型法宝经济重平衡与进度内持久战报未做。下文R5为其前序独立实验记录。

此前新增 R5 独立空中斗法评审与实验，统一结论 `docs/iterations/R5_DECISIONS.md`、最新独立验收 `R5_LAB_TESTING.md`、代码 `prototypes/r5-combat/`。PM 维护统一结论/任务/打包；策划维护 R5_DESIGN_PROPOSAL；架构维护 R5_ARCHITECTURE_PROPOSAL；开发维护实验 engine/server/README；视觉维护实验 static 与 R5_UI_PROPOSAL；QA 维护实验 tests、验收证据及 R5_LAB_TESTING。正式 game/static/data 与 v1.2 发行包不能因实验被改写；本轮实验不代表正式自动战斗、持久化迁移和经济重平衡已完成。

R4首周节奏迭代v1.2.0已完成181项全量（790.929s、无失败/跳过）和四套真实浏览器验收，同源源码归档独立解包与CRC/逐文件SHA/运行源一致性亦已通过。当前有效规则见docs/iterations/R4_DESIGN.md、R4_API.md、R4_IMPLEMENTATION.md和docs/R4_PLAYING.md：curve_v2保45基础日但首段0.5/1.5/3日；cadence恢复资格初始3/8h1/容量3；journey七段故事/三精英/手战证明；同章同难一次手胜后正式资格快捷结算。旧schema2长线先唯一备份再一次内容升级，free/schema1不静默切换。不能再以R3每日3次或旧144450总成本作为当前规则。五岗当前归属：策划r3/gameplay_config与设计路线，架构growth/cadence/storage/activities与架构测试，开发world/loot/journey，视觉static，QA其余R4/回归/浏览器，PM文档/版本/打包。最终通过数和源码hash以R4_TESTING实际记录为准。（R4/R3 中关于手动档与位置检查点的描述属v1.2单机行为，已随多用户化退役。）

R3长线版本v1.1.0已实现并验收：136项全量、晚修50项R3/15项架构回归、三个真实浏览器、16新增动作投影和独立解包运行通过，完整边界见docs/iterations/R3_TESTING.md和docs/DELIVERY.md。新Store/HTTP默认longline，旧free兼容；持续修炼、实例掉落/法宝、独立伤害世界Boss，以及主策划主动补充的高难机制/日周活动/目标引导均已落地。此结论不保证未来修改自动通过，不把模拟44.51日当真人观察。角色分工：策划r3_config/gameplay_config，开发loot/world/rules，架构growth/storage/activities与R3_API，视觉static，QA所有r3测试；PM统一版本与归档。

W1凡界版v1.0.0已按22条矩阵完成验收：冻结76项无跳过，两浏览器通过，独立解压运行通过，详COVERAGE/WORLD_TESTING。此为本版定义内容范围的结论，不代表后续扩展或未来改动自动通过。持续迭代按新发现/反馈开新轮次，保留回归和进度数据兼容，仙界仍单独下一重大版本。
