# W1 完整修仙界：已实施架构

状态：W1单机NPC世界代码已实施并冻结，数据模型见WORLD_DATA.md，公开接口见WORLD_API.md。本文保留分轮实际审查证据；最终全系统测试与浏览器验收由QA记录于WORLD_TESTING.md/WORLD_QA.md及artifacts，不把原20项通过代替新版本验收。

## 模块及共享接口
保持无安装依赖的Python/SQLite/原生前端。原realm固定0–3，原序章数据、战斗和53动作路线保持语义；后续结丹至渡劫由`state.world.stage`控制，原completed只代表序章归墟已平，不等于完整世界终局。仙界仅有版本化扩展标识，不增加可进入页面或假内容。

已实施模块与文件所有权：
- `game/world_config.py`：世界内容、境界、宗门/家族/NPC/物品/配方/事件/任务稳定ID；主策划独占维护。
- `game/world.py`：domain engine及纯投影；开发维护。若规模增长再按社会/经济/成长拆分，不一开始建通用插件系统。
- `game/rules.py`：原入口与新domain桥接，开发维护；保留旧操作机器ID，新增操作统一`world_`前缀，避免碰撞。
- `game/storage.py`（含显式迁移方法）：架构岗位负责迁移与存储持久化，与rules通过既定纯函数接口集成。
- 不实现net.py或任何实例间网络；竞技、模拟跨域赛、排行均明确标记本地NPC。
- `static/`：视觉岗位独占；所有页面消费后端pages/actions，不复制解锁和收益规则。
- `server.py`：架构岗位独占必要迁移启动接线；与开发只通过存储和规则接口协调。

已实施纯函数接口（实际Python签名无类型注解）：
```python
initial_state()                 # 返回world子树，active=False
migrate_v1(state)                # 返回完整深拷贝state，保留旧字段
validate(state)                  # 校验完整state中的world，失败ValueError
apply_action(state, action, params)  # 返回(new_state, events)
project(state)                   # 返回view.world，无存储/时间/网络副作用
```
world接口均接受完整state（initial_state除外）；migrate_v1返回完整深拷贝state，apply_action也返回完整新state，世界钱包/材料/成长/战斗仅修改嵌套world，顶层序章资源不变。validate校验world子树及legacy依赖。

`rules.apply_action`识别`world_`后委派；其余仍走原规则，但原深拷贝必须保留world。`rules.validate_state`接受精确legacy字段+world，逐层严格验证world；提供`validate_legacy_state`供迁移前校验schema1。`rules.new_game`追加initial_state；project在旧view之外增加view.world。world动作不能自行提交事务或加全局revision；成功世界实质动作由其自身在state.actions_taken计数一次，world_enter也计数一次但不推进world.tick；world_travel免费不加actions_taken/tick，UI切页及save/load不加。world.tick只世界实质动作推进，AI仅按tick结算，序章资产完全不变。事件只追加一次，维持原logs最大100条。

## state.world边界
实际world为initial_state返回的61字段对象，包含独立stage/xp/hp/mp/wallet/inventory、禀赋/功法/装备、宗门社交、四艺/家园、探索/任务、NPC/订单、模拟演武、事件/日志等；精确默认值、嵌套类型及状态机已逐项记于WORLD_DATA.md。装备以配置物品ID、库存数量与gear等级表示。灵根默认wood、体质默认renew，各含awakened=false；首次选择免费一次，后续切换按规则收费。stage为0–7，原realm不扩表；仙界仅保留content_version=1、realm_cap=渡劫、next_realm_locked=true的扩展声明。

所有对手、拍卖买家/卖家、排行榜均为本地NPC模拟，页面明确标记，不能标为真实玩家或真实跨服。用户已确认不要求联网；所有世界state可随手动档回溯，仅revision与request_id账本保持全局不回退。无需实例身份、网络nonce或独立竞技账本。

world.active默认false。原动作不推进world动态；玩家通过明确world_enter动作进入完整世界，已实施门槛为原completed=true，觉醒等从此解锁。world.stage控制后续境界，world_advance与原breakthrough独立。原realm维持3，不以索引扩展破坏原表。初始结构与全部不变量由world.validate提供。

## schema1 → schema2显式迁移
schema2迁移已实施，先备份再更新。启动发现schema1时明确提示迁移命令，`python server.py --migrate-save --data-dir ...`执行后继续启动；PM可授权当前实例执行，不必额外询问。新库直接schema2，未知高版本或坏档拒绝，不静默重置。

迁移步骤：停原服务；打开源库验证integrity/schema/legacy state和slot/请求账本；获得写入锁后，通过另一只读连接SQLite backup API创建同目录唯一`game.schema1.<id>.bak.db`（不从持有写事务的同一连接调用backup，避免阻塞）；确认备份完整且schema1内容与源一致。备份失败禁止迁移。锁内新state与slot分别migrate_v1，null保持null；旧字段逐项保持、旧revision不变、requests逐字保留；最后更新schema_version=2并校验后提交。任何异常rollback，保留原库与备份。迁移不伪造玩家行动或清空request_id。启动并发迁移必须序列化并重新检查版本，不能覆盖已生成备份。

自动备份仅在显式跨schema迁移时发生，不引入日常备份轮转。README给出停服恢复备份步骤，保留迁移失败诊断；测试必须验证state与slot都迁移、空库、空slot、请求重试、二次执行不重复迁移、注入故障回滚、坏档不改字节。

## 已确认的运行边界
用户明确选择仅单机NPC模拟。不存在真实两实例通信、联网配对、签名、nonce或联网验收，不创建net.py。界面竞技与模拟跨域赛必须显示“NPC模拟”，规则仍需真实结算而非装饰列表。

## 系统审查标准
全系统不是新增若干按钮：每个系统须具资源来源/消耗/上限、失败与恢复、持久化、页面与跨系统目标；所有随机事件如加入须有种子/状态持久化和可测机制，不能违背原确定性序章。结丹至渡劫进度要有真实门槛、功法/装备/敌人曲线与后续目标；社会系统要能产生关系与任务变化；四艺要有可用产物和市场流通，拍卖需价格/手续费/结算时机；动态事件有规则与可观察影响。开发不能用装饰性列表填“已完成”。

## 验收分层
原20测试不删不弱化；schema1真实fixture迁移及失败注入；world每领域规则与跨系统路线；全部页面真实按钮/窄屏；经济边界与重复奖励；本地NPC竞技/模拟跨域赛的阵容与结算、排行、奖励一次性及回档行为测试。未运行或未完成模块单独标明，仙界明确不实现。

## R2迁移实施与实测
已实现Store(data_dir,migrate=False)、server --migrate-save、config.SCHEMA_VERSION=2；迁移内置于storage，无新依赖。当前服务未由本岗位重启。`python -m unittest tests.test_migration -v`：12项通过（0.091秒）；覆盖原件保护、current/slot/账本/版本保留、唯一有效备份、重试原请求、二次执行、备份失败、中途SQL故障回滚、坏档、战斗快照、未知高版本、并发启动只迁移一次及真实CLI迁移后health就绪。`python -m unittest tests.test_game tests.test_rules -v`：原20项通过（6.607秒），使用临时数据目录。

以上为迁移阶段的实际运行证据；后续world代码已完成实现，完整世界的最终回归与浏览器证据以QA最新记录为准，不沿用此阶段结果作全系统结论。

## R2世界/经济初审发现（历史，当前状态以下文复查为准）
- 参数必须逐动作深校验：仅params键匹配不足以阻止list/dict值导致TypeError。所有数字拒bool，所有目标先判字符串，再字典/集合查询。
- world.validate需逐层验证quests/dialogue/disciples/npc_agents、sect_quest/event/encounter/exploration/dungeon、battle.snapshot、拍卖身份/ID/状态组合，不可只检查dict。开发已收到，待其补齐后复查。
- 拍卖NPC出价应保存实际NPC身份，玩家超价时退回其托管；NPC资金需要明确来源与回流，防长线耗尽后永久无人竞价。已报PM/开发，待设计裁决。
- 延迟拍卖退款、中奖交割、流拍返还不应使用普通gain上限截断而丢失已托管资产；建议待领取或预留容量，需在GDD与实现中明确后实测。已报PM/开发。

### 稳定checkpoint复查结果
`python -m unittest tests.test_migration tests.test_world_validation -v`：19项通过（0.168秒），含新增7项深验证方法与其畸形嵌套反例。先前容器访问异常、空battle/counters容忍等均已被ValueError守住；合法None、初态、真实野外/演武快照允许且不修改输入。参数现有SCHEMAS/_normalize统一精确键/类型/范围检查。

经济修复后的实际纯规则诊断：玩家超价将原托管退回真实NPC出价者；满钱包超价退款完整留delivery，消费腾位后领取；满背包中奖物品完整留delivery，出售腾位后完整领取，重复领取拒绝。以上路径通过；不代表所有经济与长线情境均已验收。

投影独立读取10次，输入状态深比较未变，JSON可序列化；初态173动作约10.5ms/次（当前机器、小型状态样本，非负载或长线性能承诺）。初态/战斗/器物/奇遇共见77/79个SCHEMAS动作ID，另实测自寄售未出价订单出现可用撤单入口，delivery由待领订单条件生成。全部初态fields名称唯一、与静态params不重叠、禁用有原因。六种商品在无事件/药潮/商潮及声望0/20/100样本中买价不低于卖价，通过。

寄售表单的固定药草probe误禁用已修：无药草但有矿石情境下，通用表单与真实寄售可操作；已独立运行QA对应经济回归方法验证。NPC模拟榜口径与后续真实浏览器验收由策划/QA继续核对。


### R2公开入口覆盖补验
序章入口加6个实际domain状态（入世、野外战斗、制作器物、12tick奇遇、自寄售未出价订单、满背包待领拍品）的联合投影覆盖79/79个SCHEMAS动作ID，无缺失；这是接口存在性与情境投影验证，不等于79种行为全部验收。六情境均可JSON序列化、11唯一page、fields不覆盖静态params，投影前后输入深比较相同。稳定后单独复跑world_validation：7/7通过（0.034秒），包括战斗stage8必须拒绝的反例。当前本岗位已报告缺陷均已修复复查，完整世界交付仍依赖QA全系统/浏览器与PM验收。
