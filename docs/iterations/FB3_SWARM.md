# FB3 规则层真实小怪与群战（云海御空 v2 阶段三）

## 缺口
凡界战斗一直是「本方 vs 单个敌人」。斗法台要演群战，必须先让规则层真的有小怪：小怪有自己的气血与出手，本方要选择打谁，群攻招式要真的打到多个目标。表现层只演战报，不能凭空加怪。

## 方案
- **范围**：仅长线进度（`'r3' in world`，新进度默认）的 `wild / escort / secret / guard / dungeon / elite` 战斗带小怪；`world_boss`、演武 `arena/regional`、序章（`rules.py`）与旧 free 进度保持单体。
- **数量**（`world_config.SWARMS['counts']`，按境界 `stage` 递增，`lo + min(hi-lo, stage//2)`）：野外 2–3、护送 3–4、秘境 2–3、守关劫影 3–5、副本巡守 2–3、副本镇守 4–6、支线精英 3–4。
- **预算守恒拆分（实测后定稿）**：首领保留原气血 H；每只小怪另有 `minion_hp_pct`（12%）H 的气血；原每拍期望伤害 (常击+重击)/3 中 `minion_hit_pct`（30%）划给小怪（各自固定小击，不分常击/蓄势/重击），首领常击/重击按 70% 缩放。于是「无视小怪只打首领」时拍数与承伤与旧单体一致，清小怪是减承伤、费拍数的取舍。护盾、毒、汲灵等机制仍只属于首领。
  - 初稿是「总气血守恒、首领只留 60%」：平衡表显示前瞻直接秒首领，63/112 组拍数 −50%～−67%，故改为首领保留全额气血。
- **胜负**：首领气血归零即胜，残余小怪溃散（`scatter` 事件）；奖励与战果结算不变（仍按原战斗类型/首领）。本方倒下规则不变。
- **目标**：普攻/运功强攻是单体。规则策略默认打首领（首领败亡即胜）；前瞻在原有动作维度上增加目标维度（首领、一击可收的最强小怪、最弱小怪，至多 3 个），只有收小怪的推演得分更高时才改打小怪。实测中小怪伤害占比小，前瞻几乎总是专注首领，小怪主要被群攻（焚火符、本命法宝）收掉，其余在首领败亡时溃散。
- **群攻**：焚火符与本命法宝出击对首领与每只存活小怪各结算一次（首领仍先过护盾）；同行支援只打首领。
- **减伤**：防御（×0.5）、护身符（×0.75）与镇魂符（全体停手一拍）同样作用于小怪；体质/阵法的固定减伤只作用于首领（小击本身很小）。护持法宝仍只拦首领重击。

## 数据与接口
- 进度：`world.battle` 新增可选 `minions: [{id:'m1'…, name, hp, max_hp, attack}]`（阵亡 hp=0 留在表中）。字段缺省即单体战斗——升级前已开打的战斗按旧规则打完，无需迁移。两处校验器（`validate` 与形状校验）同步放行并校验该字段。
- 校验与平衡旋钮解耦：小怪名单的上界取 `world.SWARM_KINDS` / `world.MAX_MINIONS`（结构常量，与 `world_config.SWARMS` 的取值无关），精英战只校验不变量（`max_hp` 等于精英定义、`0 ≤ attack ≤ 精英 attack`、`0 ≤ heavy ≤ 精英 heavy`、每只小怪 `1 ≤ attack`、`hp ≤ max_hp ≤ CAP`、id 为 `m1..mn` 且名称非空）。因此调整 `SWARMS['counts'|'minion_hp_pct'|'minion_hit_pct']` 不会让进行中的战斗存档在读取时变成 503；代价是校验不再重算拆分结果，改配置前后的战斗按各自开战时的数值打完。
- 战报 `battle_report`（不入库）：`enemy.units=[{id,name,max_hp}]`；每帧 `units=[{id,hp}]`；事件可带 `unit`（缺省=首领）与 `aoe:true`；新事件 `fall`（小怪伏诛）、`scatter`（首领败、残余溃散）。旧前端忽略新字段仍能播放首领。
- 视图：当前战斗分区显示存活小怪数与总气血；「下一意图」一行在首领下一招后给出「本拍预计承伤」，数值等于 `_incoming`（首领 + 存活小怪合击），与本拍真实结算一致。

## 影响分析
- `game/world.py`：`_enemy/_start`、`_round`、`_incoming`、`_decide/_candidates/_rollout`、`_auto_battle`、两处校验、战斗视图。`game/loot.py` 战斗说明。
- 精确数值测试：11 项断言单体数值，均是首领机制测试（毒、汲灵、熔炉护盾、法宝冷却/回护；`AutoBattleTreasureTests` 4 + `R3DungeonMechanicTests` 7）。这两组用 `tests/support.solo_battles` 固定为单体战斗（断言不改、注明原因），群战与这些机制的交叉面由新增 `tests/test_swarm_battle.py` 断言：`test_venom_with_a_pack_poisons_on_the_heavy_beat_and_the_pack_keeps_chipping`、`test_mana_seal_with_a_pack_drains_on_the_attack_beat_and_the_pack_keeps_chipping`、`test_furnace_barrier_absorbs_the_strike_and_the_pack_still_reaches_the_body`；R3/R4 合法路线测试未改且全部通过。
- 平衡：`scripts/swarm_balance.py` 对比同一进度、同一策略下旧（单体）与新（群战）的拍数与剩余气血，目标拍数 ±15%、剩余气血 ±10%；R3/R4 合法路线全程须仍可通过。

## 平衡结果（`python scripts/swarm_balance.py`）
7 类战斗（野外/护送/秘境/守关/副本巡守/副本镇守/精英）× 境界 0/2/4/6 × 4 策略 = 112 组，旧单体 vs 群战：**112/112 组在目标内**（拍数 ±15%、另容 1 拍取整，剩余气血 ±10% 满血比，胜负一致）。`tests/test_swarm_battle.py` 以 `--check` 方式把它纳入白盒。

## 验收
白盒全量（含路线）、平衡表、五套浏览器套件 + 真实群战回放截图；斗法台按单位演出、HUD 首领条 + 小怪图标、SVG 降级显示小怪。
