# R3运行接口（本轮实施中）

本文对应当前storage/growth/activities/loot/rules实际接口，测试结论由QA冻结后的报告给出。数据库仍schema2，两表current与requests；仅长线新增可选`state.world.r3`（version=1），旧无r3档保持自由行动，不提供旧自由档转换为长线的隐式迁移。schema1仍须原显式备份迁移。

## HTTP与模式

现有`GET /api/state`和`POST /api/new-game|action|save|load`不变。POST信封保留`request_id`与`expected_revision`，action附`action`与`params`；严格拒绝未知键/错误类型。new-game为`{request_id,expected_revision,name,mode?}`，mode仅`free|longline`，省略默认longline；纯Python `rules.new_game(name,mode='free')`保留旧默认。新局新profile_id并清手动检查点，请求账本不回退。

没有客户端时间/收益/伤害/奖励清单参数，没有测试改时钟、领取修为、离线跑经济或联网端点。Python `Store(data_dir,migrate=False,clock=None)`只向服务端测试注入UTC秒callable。world/rules行动及project接可选`context={now:int,day:'YYYY-MM-DD'}`，由Store生成；长线时钟回拨按最后结算水位钳制周期，不重新开启较早日的资格。

`view.profile={mode,load_policy}`说明当前模式及实际载入范围。原HTTP身份、Origin、JSON限制与错误码沿用docs/API.md。新错误`INCOMPATIBLE_SAVE`为422；不属于同一长线profile、已入世退回序章均拒绝。mode非法400；旧revision409；重复同ID同内容返回最新快照与duplicate=true；失败事务不写成长、资产或请求记录。

## 持续修炼

`world.r3.growth={version:1,last_settled:int|null,balance_micro:int,remainder:int,total_micro:int,rate_num:int}`。1修为=1000000微修为；积分公分母8640000000，余数严格小于它；rate_num为微修为/秒分子。未入世时不计时；成功world_enter启动。Python整数不设999999或离线仓容上限。持久状态严格核余额整点与world.xp、当前配置派生速率、水位/字段类型；domain动作扣费中间态由Store.finish协调后再提交最终校验。

GET只复制并积分预览，返回原已落盘state与基于当前可用修为生成的view/actions，不改revision/数据库/NPC/拍卖。`view.growth`：

| 字段 | 类型/单位 |
| --- | --- |
| active | bool，凡界持续修炼是否已启动 |
| settled / available | number修为，已落盘/当前权益 |
| settled_micro / available_micro | 十进制字符串，精确整数微修为 |
| last_settled | UTC整数秒或null |
| server_now | UTC整数秒锚点；回拨时不低于结算水位 |
| clock_rewound | bool；为true时UI停止平滑增量并提示等待系统时间恢复 |
| offline_gain | number修为，距上次成功落盘后的待结算增长；并非独立奖励 |
| rate | `{per_day:number,per_hour:number,numerator:string,denominator:int}`；分子/分母单位为微修为每秒 |

客户端可据当前锚点/速率平滑显示及估计时间，扣费始终由POST重算。已结算权威余额不因回拨倒扣；先GET看到未来时间预览、随后手改钟回拨时，尚未落盘的预览按当前服务端时间校正，不保证曾显示的未来预估锁定。异常时UI解释，正常流程不额外打断。POST顺序为去重→检查原revision→同步旧速率到有效now→domain动作→按实际扣除修为更新精确余额→设置新速率→state/slot/request同事务提交。换宝、根骨、功法、宗门、称号、设施、突破均不会追算整段离线新速率。待突破仍按旧阶段增长，最终封界后是潜修储备，不预支仙界。

## 手动检查点与所有权

旧free档继续完整载入。长线未入世序章可完整恢复同profile的序章检查点。入世后先同步当前成长，只恢复同profile已入世slot的安全region；若当前battle/exploration/dungeon进行中，保留当前位置并events解释。保留当前全部剧情/战斗进度、境界、修为及已花突破成本、物品/强化/拆解材料、市场/NPC经济、world.tick、活动/副本/Boss资格与所有权；没有剧情/战斗回滚能力，不用旧slotXP加累计收益公式返还消费。无安全检查点时明确拒绝，不静默吞资产。

自动持久化每次成功行动；手动slot不代替灾备。恢复整库备份/手改本机文件时间不在绝对反作弊保证内。旧大模板堆叠原样保留，不按库存数量生成数十万实例；新长线是新角色，与旧共享强化库存分开。

## 新世界动作

全部通过现有`POST /api/action`，静态params与fields值合并，fields不得覆盖静态键。数字为真正整数，不接受bool；下表是world.SCHEMAS实际新增项。战斗仍用原world_attack/power/defend/pill/fire/guard/soul/flee。

| action | params |
| --- | --- |
| world_loot_equip / enhance / quality / dismantle | `{uid:string}` |
| world_loot_unequip | `{slot:'weapon|armor|pendant|main|guard'}` |
| world_loot_choose | `{uid:string,effect_type:'cultivation|combat'}`，仅未定向法宝一次 |
| world_loot_craft_treasure | `{slot:'main|guard',effect_type:'cultivation|combat'}` |
| world_loot_exchange | `{item:'dust|enhance_material'}` |
| world_loot_claim | `{receipt:string}`，领取完整待领项 |
| world_boss_enter | `{}`，当前UTC日正式挑战 |
| world_boss_claim | `{day:string}`，可领取保留的往期新增权益 |
| world_milestone_accept | `{stage:0..7,tier:25|50|75,branch:string}` |
| world_milestone_claim | `{stage:0..7,tier:25|50|75}` |
| world_activity_accept | `{project:'expedition|artisan|social'}` |
| world_activity_week_accept | `{}`，当前UTC周唯一主题 |
| world_activity_claim | `{key:string}`，服务端已接取记录键 |
| world_dungeon_enter（长线增强） | `{dungeon:string,difficulty:1..3,chapter?:0..当前stage}`，省略chapter为当前stage |

小境界branch：25%为herb/pill，50%为alchemy/smithing/talismans/formations，75%为secret/commission；实际可选项、缺口、禁用原因以服务端fields/actions为准。旧world_cultivate在长线不发修为并拒绝，不在页面保留无限修炼按钮。旧自由模式原动作/参数保持兼容。

## 物品、Boss、页面投影

实例为`{uid,template_id,chapter,quality,enhance,effect_type,source_receipt}`，quality0..4，enhance0..3，法宝不使用战器强化。三战器槽weapon/armor/pendant与法宝main/guard独立；同uid不可占两槽。r3.instances与pending互斥持有，分解删除原实例、保留来源记录与当前材料；load不会复活原物。材料超限与背包满走原uid/材料全额pending，领取检查完整容量。副本run固定day/章节/难度/表版本/轮换seq/品质，成功才推进共享日3资格及独立难度保底，失败不推进。

世界Boss独立固定12玩家回合，服务端记录player_damage/commands，正式尝试每日最多3，取个人单次best；同周期stage/reference固定。伤害/参与/币/宝尘paid均后端权威，新成绩仅补应得差额，2R封顶。退出/失败按有效命令与实际伤害结算，空开退出无参与奖，load不重开旧run或恢复次数。

`view.world.pages`继续11页标准sections/actions。section为`{title,body,rows:[{label,value}],id?}`；action为`{id,label,params,enabled,reason,cost,effect,detail,primary,group,fields?,confirm?}`，fields为text/number/select，confirm为字符串。UI使用投影不猜资格、不自行执行奖励。长线`view.world.loot`包含mode/capacity/speed_bonus_bp/items/materials/pending/dungeons/boss/progress，items给装备前后comparison，dungeons给章节难度/资格/保底，boss给当前/最佳/已领/下一档，progress给required/阶段/ready/conditions；不是新增写接口。world_xp.max为null。

难2/3末战battle在原字段外带`mechanic/poison_turns/poison_damage/barrier`，分别对应venom/furnace_shield/mana_seal，状态随自动存档保存，不在GET重新初始化。毒按两次后续结算机会、丹清旧毒并防本回合重挂；炉盾一次且火符破盾无穿透溢出；星塔常击未防/未镇魂耗最多6MP。难1仍旧战斗流程。`view.world.battle`新增`statuses:[{label,value}]`及`counterplay:string`供明确反制提示，不让前端推演机制。世界Boss的battle另有r3_day/r3_attempt/player_damage/commands。

`view.world.goals`最多3项：`{id,title,reason,page,target_page,action:{id,params}}`，均指向实际页面行动及其静态params，客户端只导航/定位，不绕过fields、disabled或确认直接写请求。

## 活动数据及接取后观察

`r3.activities={version:1,entries:{key:entry}}`。key为`d:YYYY-MM-DD`或`w:YYYY-Www`。entry严格字段为kind/period/project/name/objectives/reward/completed/claimed/receipt/config_version；objective为kind/target/amount/label/progress。配置来自gameplay_config；日三选一，一天不可换项；周一UTC分界，1970-01-05周一起算主题按周序mod3。

仅接取后成功行动observe；不把已有库存/过去战果追算。支持实际采集、四艺制造/使用、完整秘境/副本、有效正式Boss、宗门材料/正式委托及chat/gift/consult社交。每个目标各自累计，练习副本可计通关目标但不新增掉落资格。未完成过期不再累计、不阻新期；已完成过期权益仍可领取；奖励只有配置材料，不给XP/增速/额外资格。claimed与receipt及完整材料发放/待领同事务，唯一receipt为activity:profile_id:key。

`activities.initial_state()`、`observe(before_w,after_w,action,params,context)`、`handle(w,action,params,events,context)`、`project(state,context)`、`validate(state)`已接领域。project返回sections/actions并合并quests页，同时view.world.activities.sections可读；总览id为r3_daily/r3_weekly，记录id为r3_activity:key，前端可置顶展开。所有周期GET只投影，不推进计数或领取。

## 当前证据与交付边界

架构精确积分9项、活动纯模块6项已实际通过；独立QA成长HTTP10项亦由架构复跑通过。前一并行修改窗口组合88项中原76无失败，1新profile收到临时500；完成接口接入后已单独重跑growth9+activities6+profile3共18项全过，临时500未再复现，仍不代替冻结后的全量验收。架构已实际完成新增活动64revision真实HTTP链：完整序章入世→接日常百工试锋→制作并实际装备→Boss有效攻击后退出→领奖宝尘1/强化材2，三类活动section id均在quests页。该路径仍须QA独立复测；完整最终回归/浏览器与长线玩法覆盖继续由QA验证，本文件不替代最终测试报告。
