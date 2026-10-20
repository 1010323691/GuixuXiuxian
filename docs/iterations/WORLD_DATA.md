# W1 实际数据模型与状态契约

本文件按冻结后的 `game/world.py` 的 `initial_state`、`_validate_state`、`_deep_validate`、`SCHEMAS`、`project` 和 `game/storage.py` 整理。数据库schema为2，`world.version`为2，内容版本为1。这里描述实际字段和行为；数值、内容ID与叙事见 `world_config.py` 与 `WORLD_DESIGN.md`，公开投影见 `WORLD_API.md`。

## 持久化、资产与时间归属
数据库仍只有两表：`current(id=1,schema_version,revision,state,slot)` 与 `requests(request_id,payload)`。state和slot是JSON字符串，未开局/无手动档各为JSON null；requests保存包含endpoint和完整原始请求的规范化载荷。没有独立网络身份、真实玩家账号或跨服账本。

state保留序章字段，并且只新增一个world对象。序章realm始终0–3；进入世界后，姓名、境界、hp/mp、修为、序章资源、首胜、completed等序章资产冻结，世界使用自己的hp/mp/xp/wallet/inventory/stage。顶层actions_taken和logs继续是全游戏历史，属于计数/记录，不是序章资产。

| 操作 | global revision | 顶层actions_taken | world.tick/规则AI |
| --- | --- | --- | --- |
| 有效序章行动 | +1 | +1；序章travel除外 | 不推进 |
| world_enter（原completed必须true，active必须false） | +1 | +1 | 不推进；一次初始化入世行囊与NPC订单 |
| 有实质效果的其他世界行动 | +1 | +1 | tick+1后结算AI/到期/生产 |
| world_travel | +1 | 不变 | 不推进 |
| 手动save/load、新局 | +1 | save不变；load恢复档内计数；新局归0 | 不额外推进；load恢复world快照 |
| GET/切页/失败/同ID同载荷重试 | 不变 | 不变 | 不推进 |

world.active初始false。入世要求序章通关，赠世界钱包60与草6/矿6/木6/晶2，不复制序章财富。active阻止重复领取；手动回档可回到此前游戏事实，global revision/请求账本始终不回退。所有NPC、拍卖、排行榜、演武和三域赛均为本地模拟。

## world初始对象（实际61个字段）
以下直接摘录冻结代码的 `initial_state()` 返回值，不是额外schema或推荐字段。整数不接受bool；通用世界数量上限CAP=999999，具体更小范围见后文。

```json
{
  "version": 2,
  "active": false,
  "stage": 0,
  "xp": 0,
  "hp": 200,
  "mp": 60,
  "wallet": 0,
  "inventory": {},
  "root": {
    "id": "wood",
    "level": 0,
    "points": 0,
    "awakened": false
  },
  "constitution": {
    "id": "renew",
    "level": 0,
    "awakened": false
  },
  "skills": {
    "origin": 1
  },
  "skill": "origin",
  "equipment": {
    "weapon": null,
    "armor": null,
    "pendant": null
  },
  "gear": {},
  "arts": {
    "alchemy": 0,
    "smithing": 0,
    "talismans": 0,
    "formations": 0
  },
  "factions": {},
  "sect": null,
  "contributions": {},
  "contribution_total": 0,
  "sect_quest": null,
  "sect_earned": {},
  "relations": {},
  "friends": [],
  "companion": null,
  "master": null,
  "disciples": {},
  "family": null,
  "family_members": [],
  "family_buildings": {
    "garden": 0,
    "guard": 0,
    "school": 0
  },
  "family_builds": 0,
  "family_renown": 0,
  "home": {
    "garden": 0,
    "workshop": 0,
    "chamber": 0
  },
  "home_storage": {
    "garden": 0,
    "workshop": 0,
    "chamber": 0
  },
  "home_origin": {
    "garden": 0,
    "workshop": 0,
    "chamber": 0
  },
  "arrays_enabled": {
    "spirit": true,
    "mountain": true,
    "seal": true
  },
  "arrays": {
    "spirit": 0,
    "mountain": 0,
    "seal": 0
  },
  "region": "qinglan",
  "exploration": null,
  "dungeon": null,
  "battle": null,
  "guard_wins": [],
  "secret_wins": [],
  "dungeon_wins": [],
  "quests": {},
  "dialogue": {},
  "achievements": [],
  "title": null,
  "arena": {
    "points": 0,
    "claims": [],
    "wins": 0,
    "season": 0,
    "regional_points": 0,
    "growth": 0,
    "current": null
  },
  "auctions": [],
  "auction_seq": 0,
  "npc_agents": {},
  "event": null,
  "encounter": null,
  "event_seq": 0,
  "tick": 0,
  "counters": {
    "battles": 0,
    "crafts": 0,
    "teaching": 0,
    "gathers": 0,
    "wins": 0
  },
  "last_chat": {},
  "last_teach": -3,
  "journal": [],
  "ending": false,
  "extension": {
    "content_version": 1,
    "realm_cap": "渡劫",
    "next_realm_locked": true
  }
}
```

## 类型、内容ID与嵌套约束

| 字段组 | 实际类型与约束 |
| --- | --- |
| version / active / ending | version为整数2；active/ending为bool；active要求序章completed；ending要求stage7且guard_wins含字符串"7" |
| stage / xp / hp / mp / wallet | stage整数0–7；xp/wallet整数0–CAP；hp整数1–派生上限，mp整数0–派生上限；无客户端直接赋值入口 |
| inventory | `{资源或ITEMS ID: int 0–CAP}`；禁止stone键，灵石只能在wallet；不认识的ID拒绝 |
| root | 精确 `{id,level,points,awakened}`；id为ROOTS已知字符串（不为null），level0–3、points0–2、awakened为bool |
| constitution | 精确 `{id,level,awakened}`；id为CONSTITUTIONS已知字符串（不为null），level0–3、awakened为bool |
| skills / skill | `{SKILLS ID: int 1–3}`及已学的当前SKILLS ID；初始origin1 |
| gear / equipment | gear为有实际inventory库存的器物ID→等级，运行制造/强化为1–3（校验数值表允许0–3）；equipment精确weapon/armor/pendant三槽，每槽null或已有gear且库存≥1、slot相符的ID；无独立随机实例ID |
| arts | 精确alchemy/smithing/talismans/formations四项熟练度整数；等级由熟练度派生，不存另一份等级 |
| factions / relations | 已知REGIONS或NPCS ID→0–100；不认识的ID拒绝 |
| sect / contributions / sect_earned / contribution_total | sect为null或SECTS ID；contributions为分宗可花贡献，sect_earned为分宗历史，contribution_total为总历史；非负整数；当前sect必须在前两表中存在 |
| friends / family_members / companion / master | friends/family_members为去重已知NPC ID列表；companion为null或已结交的NPC；master为null或已知NPC；均非真人权限 |
| family / family_buildings / family_builds / family_renown | family为null或长度1–16字符串；设施精确garden/guard/school、等级0–3；历史次数和声望非负整数；无家族时不得残留成员或非零家族设施 |
| home / home_storage / home_origin | 三表都精确garden/workshop/chamber；home等级0–3；仓库0–20×该设施等级；origin为0–当前tick；生产基于各自起点，每3个有效世界行动发生，升级不补历史产物 |
| arrays / arrays_enabled | 精确spirit/mountain/seal；等级0–3和bool启停表，属性由等级与开关派生，不回合叠加写入 |
| region | 已知REGIONS ID，初始qinglan；只改世界位置，不改序章region |
| guard_wins / secret_wins / dungeon_wins | 去重字符串列表；分别为不超过当前stage的"0"…"7"、已知SECRETS ID、已知DUNGEONS ID加":1/2/3" |
| quests / dialogue / achievements / title | quests见状态机；dialogue为已知NPC ID→字符串（当前剧情主要由关系/任务事实派生）；achievements为已知成就kind+":0/1/2"去重列表；title为null或TITLES ID |
| auction_seq / event_seq / tick | 非负整数至CAP；订单ID来自递增auction_seq，事件轮换来自event_seq；无系统时钟参与 |
| counters / last_chat / last_teach / journal | counters精确battles/crafts/teaching/gathers/wins非负整数；last_chat为字符串键到非负回合数的表，实际动作只写NPC ID；last_teach整数−3至CAP；journal只保留最近100条字符串，顶层logs也至多100条 |
| extension | 固定 `{content_version:1,realm_cap:"渡劫",next_realm_locked:true}`；用于表明版本上限，不含可游玩的仙界内容 |

friends、family_members、guard_wins、secret_wins、dungeon_wins、achievements这六组顶层记录列表最多1000项且无重复；journal单独限制100条。arena.claims由自己的去重校验管理，不套用该1000条上限。存档包含不受支持的world字段、嵌套类型、内容ID或范围时，validate以ValueError拒绝；不会修复、删字段或静默建新角色。表中同时区分了运行时约束与校验器实际范围，不能据此声称防止本机管理员改档。

## 活动与状态机

**主线/支线任务**：`quests[quest_id]`缺键表示未接；接取变`active`，满足配置条件并一次性扣交付物/发奖后变`claimed`。重复接取或领奖拒绝。交付器物只移走未装备的可交付副本；若仍有该器库存，gear等级与已装备副本保留。任务列表和按钮从后端事实派生，没有独立可篡改的“可领奖”布尔。

**宗门**：散修sect=null → join已知宗门并建立可用/历史账本 → 在当前宗门接受委托。`sect_quest`为null或精确`{type:"battle|craft|secret",done:bool}`；只计算接取后的目标，完成置done=true，交付发一次奖励后归null。退出清除当前sect与未交委托，分宗可用贡献/历史不挪给其他宗门；退出后不能借旧权限领奖或兑换。

**弟子派遣**：`disciples[DISCIPLES ID]={xp:int,mission:null|{item:"herb|ore|crystal",end:int}}`，最多3名。招收后可授业；派遣把mission置为tick+3到期，不能同时授业/再派遣。到期仍保留mission等待手动领取，领取奖励一次后归null；取消归null且无奖；有派遣时不能直接解除师徒。

**秘境**：`exploration=null|{id:SECRETS ID,node:0|1|2}`，依次勘察、采集/修整、守卫；胜利或撤离清空。**副本**：`dungeon=null|{id:DUNGEONS ID,difficulty:1..3,stage:0..7,round:0..2}`，stage为入场快照，三战后清空并标记首通，战间可安全准备；不能同时有秘境与副本。

**动态事件与奇遇**：`event=null|{id:"herb|beast|trade",name:str,end:int}`；每20tick确定性轮换，持续6tick。`encounter=null|{id:"traveler|furnace|inscription",end:int}`；每12tick如当前无奇遇则生成，按event_seq轮换，6tick到期。查看或离线不会推进，选择成本/效果由配置和后端结算。

## 拍卖、NPC与托管归属
`auctions`是订单列表，每项精确：
```text
{id:str数字ID, item:已知物品/资源ID, quantity:int>=1,
 base:int1..1000, price:int0..CAP,
 bidder:null|"player"|具体NPC ID, seller:"player"|具体NPC ID,
 end:int, settled:bool, cancelled:bool, last_bid:int,
 delivery:{物品或资源ID:int0..CAP}}
```
NPC实际ID为healer/smith/stargazer，不存含糊的"npc"。卖家不能竞拍自己的订单；无人出价时price=0，有出价时price≥base。新订单托管实际货物；玩家寄售最多3活跃单，总活跃最多12。当前校验列表最多100条，订单创建器另有120条保留上限；正常历史清理只保留最近60个已完成且无待领的订单，未结束或有delivery的记录不按历史窗口删掉。

状态按布尔字段表示：活跃（两标志false）→领先出价及last_bid更新→到期settled=true；无出价的本人寄售也可cancelled=true。玩家出价托管全额，自己加价只付差额；外人超价时退给实际旧bidder。NPC不在玩家同一行动立刻超价，expiry时先交割再考虑新出价。成交卖家收price−floor(price/20)，无买家返货；不能再撤销或重复结算。

玩家收货/退款超容量时，完整数量留在该订单delivery，不截断；`world_delivery`检查整笔容量后一次全部发放并清空，容量不足不改、再次领取拒绝。NPC也有独立溢出托管：
```text
npc_agents[NPC ID] = {
  wallet:int0..200, inventory:{已知物品/资源ID:int0..200},
  turns:int0..CAP, last:str(<=1000字符),
  pending:{已知物品/资源ID:int0..CAP}
}
```
active世界必须有全部配置NPC。NPC钱包/库存上限200，超过进入该NPC的pending，后续世界行动先尝试转回可用容量；不凭空销毁退款或货物。NPC按轮流行动采集缺料、按配方制作、寄售、竞价；来源、消费和托管均在同一世界state，可手动回档，没有真正跨玩家资产。

## 战斗快照与赛季
world.battle为null或精确：
```text
{name:str, hp:int1..max_hp, max_hp:int, attack:int, heavy:int,
 turn:int, kind:"wild|guard|secret|dungeon|arena|regional|escort",
 target:str, stage:int0..7, shield:int0..2, heals:int0..2,
 snapshot:null|{hp:int1..玩家上限,mp:int0..玩家上限,inventory:{已知物品ID:int0..CAP}},
 start_tick:int0..当前tick, growth:int0..10}
```
secret/dungeon的target必须对应当前活动；arena/regional的target为ARENA_OPPONENTS ID。普通战斗snapshot=null；演武与赛季保存玩家开战hp/mp及模拟耗材库存。战斗内丹符只扣snapshot.inventory，真实world.inventory仍可接收拍卖交割等收益；结束/撤退/败退只恢复开场hp/mp，不覆盖真实背包。turn%3决定常击/蓄势/重击；击杀先结胜利不反击，普通败退留1血、安全地恢复，模拟战不永久损耗真实丹符。

`arena`精确包含points、claims、wins、season、regional_points、growth、current。计分为非负整数；growth0–10；claims为普通演武的去重字符串，键为`arena:opponent_id:floor(start_tick/20)`。周期按开场tick固定，同周期每模板只发一次积分/灵石。

`current=null|{id:int1..season,stage:0..7,round:0..3,claimed:bool,npc_scores:{全部ARENA_OPPONENTS ID:int0..10},growth:0..10}`。报名锁stage/growth并清本季成绩；未结算旧季不能新报名。每场胜利round+1，败退可重试并记实际NPC赛果；3胜后可一次领取冠军奖励，再开下一季。冠军增长后续NPC成长，不倒改本季快照。模拟榜明确NPC行为经验折算或本季真实模拟赛果，绝不声称真人或全球排名。

## 79种动作的代码目录与页面
唯一可执行参数目录是 `game/world.py:SCHEMAS`，`_normalize`负责精确键集合/类型/范围，具体条件再由对应处理器校验。下表由冻结SCHEMAS逐项生成，共79项；页面入口来自project/rules.project，战斗指令在普通战斗放exploration、模拟战放arena。条件性按钮（奇遇、已有器物、撤单、待领）仅在对应事实存在时生成。

参数缩写：str为非空字符串（通用长度≤128，姓名等业务再收紧）；qty为整数1–20；difficulty为整数1–3；price为整数1–1000；bid为整数1–CAP；tier为整数0–2。所有整数拒bool。`world_craft.quantity`省略时后端补1，其余仍必须满足SCHEMAS精确键；前端只提交服务端params及fields值，不猜目录。

| action | params（空为{}） | 入口page |
| --- | --- | --- |
| `world_enter` | `{}` | 序章全局入口 |
| `world_cultivate` | `{}` | character |
| `world_rest` | `{}` | character |
| `world_gather` | `item:str` | world |
| `world_travel` | `region:str` | world |
| `world_root` | `choice:str` | character |
| `world_constitution` | `choice:str` | character |
| `world_root_train` | `{}` | character |
| `world_constitution_train` | `{}` | character |
| `world_dew` | `{}` | character |
| `world_skill_learn` | `skill:str` | character |
| `world_skill_equip` | `skill:str` | character |
| `world_skill_upgrade` | `skill:str` | character |
| `world_advance` | `{}` | character |
| `world_finish` | `{}` | character |
| `world_craft` | `recipe:str, quantity:qty` | craft |
| `world_equip` | `item:str` | character |
| `world_unequip` | `item:str` | character |
| `world_forge` | `item:str` | character |
| `world_home` | `facility:str` | estate |
| `world_home_collect` | `facility:str` | estate |
| `world_family_build` | `facility:str` | social |
| `world_array_toggle` | `array:str` | craft |
| `world_sect_join` | `sect:str` | sects |
| `world_sect_leave` | `{}` | sects |
| `world_sect_daily` | `item:str` | sects |
| `world_sect_redeem` | `reward:str` | sects |
| `world_sect_accept` | `type:str` | sects |
| `world_sect_claim` | `{}` | sects |
| `world_chat` | `npc:str` | social |
| `world_gift` | `npc:str` | social |
| `world_friend` | `npc:str` | social |
| `world_companion` | `npc:str` | social |
| `world_master` | `npc:str` | social |
| `world_master_leave` | `{}` | social |
| `world_consult` | `npc:str` | social |
| `world_family_invite` | `npc:str` | social |
| `world_family_create` | `name:str` | social |
| `world_family_dissolve` | `{}` | social |
| `world_family_remove` | `npc:str` | social |
| `world_companion_leave` | `{}` | social |
| `world_disciple` | `disciple:str` | social |
| `world_teach` | `disciple:str` | social |
| `world_dispatch` | `disciple:str, destination:str` | social |
| `world_collect_disciple` | `disciple:str` | social |
| `world_cancel_dispatch` | `disciple:str` | social |
| `world_disciple_release` | `disciple:str` | social |
| `world_hunt` | `{}` | exploration |
| `world_boss` | `{}` | exploration |
| `world_secret_enter` | `secret:str` | exploration |
| `world_secret_step` | `choice:str` | exploration |
| `world_secret_leave` | `{}` | exploration |
| `world_dungeon_enter` | `dungeon:str, difficulty:difficulty` | exploration |
| `world_dungeon_next` | `{}` | exploration |
| `world_dungeon_leave` | `{}` | exploration |
| `world_encounter` | `choice:str` | exploration |
| `world_buy` | `item:str, quantity:qty` | market |
| `world_sell` | `item:str, quantity:qty` | market |
| `world_auction_list` | `item:str, quantity:qty, price:price` | market |
| `world_auction_bid` | `auction:str, price:bid` | market |
| `world_auction_cancel` | `auction:str` | market |
| `world_delivery` | `auction:str` | market |
| `world_quest_accept` | `quest:str` | quests |
| `world_quest_claim` | `quest:str` | quests |
| `world_achievement` | `kind:str, tier:tier` | achievements |
| `world_title` | `title:str` | achievements |
| `world_arena` | `opponent:str, mode:str` | arena |
| `world_season_join` | `{}` | arena |
| `world_season_fight` | `{}` | arena |
| `world_season_claim` | `{}` | arena |
| `world_wait` | `{}` | world |
| `world_attack` | `{}` | exploration / arena（按战斗kind） |
| `world_power` | `{}` | exploration / arena（按战斗kind） |
| `world_defend` | `{}` | exploration / arena（按战斗kind） |
| `world_pill` | `{}` | exploration / arena（按战斗kind） |
| `world_fire` | `{}` | exploration / arena（按战斗kind） |
| `world_guard` | `{}` | exploration / arena（按战斗kind） |
| `world_soul` | `{}` | exploration / arena（按战斗kind） |
| `world_flee` | `{}` | exploration / arena（按战斗kind） |

## 事务顺序与异常边界
1. HTTP校验Host/Origin/同源自定义头、Content-Type、16KiB体上限、有限JSON数值与对象形状；存储校验request_id/expected_revision及端点字段。
2. 独立SQLite连接开启BEGIN IMMEDIATE，先查请求账本并读/校验当前state/slot。同ID同载荷直接返回最新投影、duplicate=true、events=[]；异载荷409；其后版本不符409。
3. 纯规则在深拷贝上校验权限/动作参数并扣费、应用玩家效果。有效世界行动递增tick和全局行动数，结算NPC pending、到期拍卖、设施生产、NPC生产/竞价、动态事件/奇遇，截取日志。
4. 完整校验候选state/slot，同事务写入state、slot、revision+1和request账本；构建投影后commit，只有提交成功才HTTP成功。任一步异常rollback，不能发布部分扣款或奖励。
5. save复制完整state到slot；load只恢复游戏state、不恢复revision/requests；新局重建完整state且清slot、保留账本。

400用于字段/类型错误，422用于当前规则条件拒绝，409用于版本/ID冲突，503用于SQLite/IO/存档读取写入失败，500用于未预期服务错误；失败不显示已保存。坏档/未知schema启动拒绝并保留原件；schema1必须显式迁移前生成唯一且校验过的SQLite备份，state和slot一起升级，旧字段、revision及requests保持。迁移不是一次游戏行动，不生成奖励。

## 实证与交付边界
本岗位已执行迁移12项、深校验7项及对应故障/经济诊断，记录见WORLD_ARCHITECTURE；79/79动作ID公开投影可达已用多种实际情境核对，不等于每个参数排列皆验收。最新全量测试、浏览器与完整通关由QA单独记录于WORLD_TESTING/WORLD_QA及artifacts；本文不将仍运行的最终验收提前记为通过。无真人联机、真实货币、离线收益或仙界内容。
