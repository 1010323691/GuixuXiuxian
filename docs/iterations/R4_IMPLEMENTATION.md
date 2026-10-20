# R4 实施方案与交接

状态：接口协调中，尚未宣称实现或测试通过。开发拥有 world.py、loot.py、rules.py、新 journey.py；不修改配置、存储、前端或 QA 文件。

## 最小可实装闭环

1. 架构维护 cadence.py 和存档升级：初始3资格、上限3、每8小时恢复1，预约占容量；GET只预览，真实变更与revision、请求账本同事务。loot.begin_run预约，complete_run成功消费，撤离/败退释放。旧daily只保历史，零资格手战仍可练习。
2. world_dungeon_sweep 参数 dungeon/chapter/difficulty。只允许同章同难已有一次真实手战胜利，仍要求地域、章节、难度与装备分；必须有资格且无战斗/探索。调用同一run计划与最终通关结算，复用实例、材料、保底、容量托管、普通重复奖励，计已接副本任务；不生成首次通关、不增加手战证明、不扫世界Boss。
3. journey.py 管理七段串联故事与三名独立精英。建议日仅建议，无日历锁；前段已领奖、最低境界及实际行为解锁，接取后计数，完成永久可领。故事奖励走现有唯一实例与满仓托管，不推进副本序列/保底。精英用固定章数/固定敌强与既有盾、毒、汲灵反制，免费重试，不消耗资格。
4. 现有 pages/actions 是唯一写入口。新增资格摘要、故事分层/精英状态、扫荡条件与准确奖励均为后端只读投影；前端不从中文推导规则。

## 关键兼容与风险

- 架构一次备份事务升级 current/slot；开发不另做启动迁移。旧 free 保持旧行为。旧 R3 dungeon_wins 均为真实手战，可迁移为独立 manual_clears；扫荡永不扩增该证明。
- 所有退出路径都释放预约，成功结算幂等且保底只推进一次；中断run保留已冻结奖励配置。不能在预约阶段消耗成功计数，也不能练习成功刷实例。
- 原 world._victory 内普通首通/重复奖励必须抽出共用，避免扫荡只拿实例却漏普通收益或重刷首通。
- 实例满200、物品暂存199且材料满时，单run最后击杀仍须完整托管；延续R3物品暂存与材料待领分开容量的保证。
- 故事任务只观察接取后的真实成功，不追溯，不以点击空操作计数。三阵满级时不能留下不可完成的制造目标；有效启阵有实际变化才计。
- 新成长成本与旧余额比例迁移由growth负责；开发仅消费冻结成本表，不自行改变时间或引入行动XP。

## 待冻结与验证重点

策划提供故事/精英配置schema；架构提供cadence完整state校验及迁移接口。QA应独立验证8小时边界/回拨/重启、失败释放、零资格练习与禁扫、扫荡与手战结算等价、不同章难不可借用证明、请求重放不重复掉落、满仓材料组合、七段逐段合法完成和三精英反制。当前仅完成代码审阅，R4测试尚未运行。

## 开发检查点（实施后）

已实现 `game/journey.py`、world共用副本最终结算/扫荡/精英战斗、loot恢复资格挂钩与全量投影。新增动作：`world_dungeon_sweep{dungeon,chapter,difficulty}`、`world_story_accept{story}`、`world_story_claim{story,item?}`、`world_elite_enter{elite}`。装备选择为 blade/armor/pendant；三精英为 caravan_guard/venom_keeper/astral_warden。

`view.world.loot.credits`直接使用cadence投影；每副本`sweep`给enabled/reason/consume/preview/action。`view.world.journey.layers`含id/title/recommended_day/unlock/status/objectives/rewards/action；elites含id/title/status/preparation/rewards/action。标准故事操作在quests页，精英和扫荡在exploration页，所有实际写入仍走统一action事务。

实际验证：`python -m unittest tests.test_r3_items tests.test_r3_profiles -q` 12项通过。开发临时执行器沿原53行动合法开局，接首段→制造/装备灵刃→手战三场→领故事奖→扫荡，恢复资格3→2→1，保底1→2，手战证明仅den:0:1；第一次自行全强攻策略失败释放预约，调整为重击防御后合法胜出，未降低敌强。独立受控fixture检查炉盾精英固定数据/投影/撤退，通过；这不是实际支线合法通关证据。QA与策划正在独立公开路线验证，尚未据此宣布R4交付。

s6明确只计难2/3真实手战；一般副本故事和活动允许扫荡。s7只计正式Boss已结算、至少1指令且个人伤害大于0；次数耗尽等下一日补做，不开新的练习Boss路径。commission依据daily_count成功增量；奖励不会发行动XP。旧缺journey/cadence仅容许进入架构一次升级，运行新档始终含二者。

补充回归：`tests.test_world_validation tests.test_r3_rewards`共11项中9通过；2旧奖励测试只改变day字符串即期待UTC重置，与本轮批准的8小时恢复权威不符。已交QA保持模板/第10保底等有效断言，改为注入真实context.now与恢复规则；未以这2项失败宣称全通过。另修free坏档伪造elite挑战被拒绝，不影响合法free。

架构交叉审查修复：装备故事source凭证数量严格等于claimed（防已发装备却伪造未领奖），核对选择模板/原品质及仍持有实例章节；精英战斗须对应未领奖故事、未有战胜记录且地域吻合。交叉校验置于loot容器/凭证/run结构检查之后。最新定向`world_validation + r3_items + r3_profiles` 19项通过。最终版本仍以独立QA当轮hash证据为准。

旧free完整世界回归完成：`python -m unittest tests.test_world_systems -q` 14项全部通过，281.467秒，exit0（含合法完整凡界路线）。此回归进程在开发集成期间运行，最终R4完整验收仍由QA对冻结代码独立执行；生产文件已停止主动功能更改，仅响应明确缺陷。

PM入口审查补修：总览目标纳入真实enabled故事领奖/接取/精英候选；优先级为战斗→故事及活动待领奖→可突破→故事可接/精英→既有装备与其他目标，仍最多3，点击仅导航。定向检查初态可接、完成可领、精英可挑战、战斗优先四种状态，每个goal均唯一匹配对应pages/action/id/params，检查通过。仅loot目标投影变化，写入规则未改；已通知QA及视觉。
